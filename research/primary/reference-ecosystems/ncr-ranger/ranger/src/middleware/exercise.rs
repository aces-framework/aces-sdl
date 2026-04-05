use crate::{
    errors::RangerError,
    middleware::authentication::User,
    models::{helpers::uuid::Uuid, Exercise},
    roles::RangerRole,
    services::database::exercise::GetExercise,
    utilities::{create_database_error_handler, create_mailbox_error_handler},
    AppState,
};
use actix_http::HttpMessage;
use actix_web::{
    dev::{forward_ready, Service, ServiceRequest, ServiceResponse, Transform},
    web::Data,
    Error, FromRequest,
};
use futures_util::future::LocalBoxFuture;
use log::{debug, error};
use std::{
    future::{ready, Ready},
    rc::Rc,
};

use super::keycloak::{KeycloakAccess, KeycloakInfo};

pub struct ExerciseInfo(pub Exercise);

impl ExerciseInfo {
    pub fn into_inner(self) -> Exercise {
        self.0
    }
}

impl FromRequest for ExerciseInfo {
    type Error = Error;
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(
        req: &actix_web::HttpRequest,
        _payload: &mut actix_web::dev::Payload,
    ) -> Self::Future {
        let value = req.extensions().get::<Exercise>().cloned();
        let result = match value {
            Some(v) => Ok(ExerciseInfo(v)),
            None => Err(RangerError::KeycloakQueryFailed.into()),
        };
        ready(result)
    }
}

impl std::ops::Deref for ExerciseInfo {
    type Target = Exercise;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

pub struct ExerciseMiddlewareFactory;

impl<S, B> Transform<S, ServiceRequest> for ExerciseMiddlewareFactory
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error> + 'static,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type Transform = ExerciseMiddleware<S>;
    type InitError = ();
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ready(Ok(ExerciseMiddleware {
            service: Rc::new(service),
        }))
    }
}

pub struct ExerciseMiddleware<S> {
    service: Rc<S>,
}

impl<S, B> Service<ServiceRequest> for ExerciseMiddleware<S>
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error> + 'static,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type Future = LocalBoxFuture<'static, Result<Self::Response, Self::Error>>;

    forward_ready!(service);

    fn call(&self, req: ServiceRequest) -> Self::Future {
        let service = self.service.clone();
        let user = req.extensions().get::<Rc<User>>().cloned();
        let keycloak_access = req.extensions().get::<Rc<KeycloakAccess>>().cloned();
        let app_state = req.app_data::<Data<AppState>>().cloned();

        Box::pin(async move {
            let user = user.ok_or_else(|| {
                error!("User not found");
                RangerError::UserInfoMissing
            })?;
            let keycloak_info = KeycloakInfo(keycloak_access.ok_or_else(|| {
                error!("Keycloak access not found");
                RangerError::KeycloakQueryFailed
            })?);
            let app_state = app_state.ok_or_else(|| {
                error!("App state not found");
                RangerError::AppStateMissing
            })?;
            let exercise_uuid =
                Uuid::try_from(req.match_info().get("exercise_uuid").ok_or_else(|| {
                    error!("Exercise uuid not found");
                    RangerError::UuidParsingFailed
                })?)
                .map_err(|_| {
                    error!("Invalid exercise uuid");
                    RangerError::UuidParsingFailed
                })?;

            let exercise = app_state
                .database_address
                .send(GetExercise(exercise_uuid))
                .await
                .map_err(create_mailbox_error_handler("Database"))?
                .map_err(create_database_error_handler("Get exercises"))?;

            let exercise = match user.role {
                RangerRole::Admin => std::result::Result::Ok(exercise),
                RangerRole::Participant => {
                    let is_member = exercise
                        .is_member(
                            user.id.clone(),
                            keycloak_info,
                            app_state.configuration.keycloak.realm.clone(),
                        )
                        .await
                        .map_err(|err| {
                            error!(
                                "Failed to check if user is a member of the exercise: {}",
                                err
                            );
                            RangerError::ExericseNotFound
                        })?;
                    if is_member {
                        std::result::Result::Ok(exercise)
                    } else {
                        debug!("User is not a member of the exercise");
                        Err(RangerError::ExericseNotFound)
                    }
                }
                RangerRole::Client => {
                    return Err(RangerError::AccessForbidden.into());
                }
            }?;
            req.extensions_mut().insert(exercise);

            let res = service.call(req).await?;
            Ok(res)
        })
    }
}
