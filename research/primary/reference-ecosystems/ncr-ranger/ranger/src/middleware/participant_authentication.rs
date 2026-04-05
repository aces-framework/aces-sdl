use super::authentication::User;
use crate::{
    errors::RangerError,
    models::Deployment,
    services::database::participant::GetParticipants,
    utilities::{create_database_error_handler, create_mailbox_error_handler},
    AppState,
};
use actix_http::HttpMessage;
use actix_web::{
    dev::{forward_ready, Service, ServiceRequest, ServiceResponse, Transform},
    web::Data,
    Error,
};
use futures_util::future::LocalBoxFuture;
use log::{error, warn};
use std::{
    future::{ready, Ready},
    rc::Rc,
};

pub struct ParticipantAccessMiddlewareFactory;

impl<S, B> Transform<S, ServiceRequest> for ParticipantAccessMiddlewareFactory
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error> + 'static,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type Transform = ParticipantAccessMiddleware<S>;
    type InitError = ();
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ready(Ok(ParticipantAccessMiddleware {
            service: Rc::new(service),
        }))
    }
}

pub struct ParticipantAccessMiddleware<S> {
    service: Rc<S>,
}

impl<S, B> Service<ServiceRequest> for ParticipantAccessMiddleware<S>
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
        let app_state = req.app_data::<Data<AppState>>().cloned();

        Box::pin(async move {
            let app_state = app_state.ok_or_else(|| {
                error!("App state not found");
                RangerError::AppStateMissing
            })?;

            let deployment = req
                .extensions()
                .get::<Deployment>()
                .cloned()
                .ok_or_else(|| {
                    error!("Deployment not found");
                    RangerError::DeploymentNotFound
                })?;
            let user = req.extensions().get::<Rc<User>>().cloned().ok_or_else(|| {
                error!("User not found");
                RangerError::UserInfoMissing
            })?;

            let entity_selector = req.match_info().get("entity_selector").ok_or_else(|| {
                error!("Entity selector not found");
                RangerError::EntityNotFound
            })?;

            let is_authorized = app_state
                .database_address
                .send(GetParticipants(deployment.id))
                .await
                .map_err(create_mailbox_error_handler("Database"))?
                .map_err(create_database_error_handler("Get participants"))?
                .iter()
                .any(|participant| {
                    participant.user_id.eq(&user.id) && participant.selector.eq(&entity_selector)
                });

            if !is_authorized {
                warn!(
                    "User {:?} is not authorized to access entity selector: '{}'",
                    user.id, entity_selector
                );
                return Err(RangerError::NotAuthorized.into());
            }

            let res = service.call(req).await?;
            Ok(res)
        })
    }
}
