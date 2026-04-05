use crate::{
    errors::{PackageServerError, ServerResponseError},
    services::database::{apitoken::GetTokenByToken, Database},
    AppState,
};
use actix_http::HttpMessage;
use actix_web::{
    dev::{forward_ready, Service, ServiceRequest, ServiceResponse, Transform},
    http::header::HeaderValue,
    web::Data,
    Error, FromRequest,
};
use futures_util::future::LocalBoxFuture;
use log::error;
use serde::{Deserialize, Serialize};
use std::{
    future::{ready, Ready},
    rc::Rc,
};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct UserToken {
    pub id: String,
    pub email: String,
}

#[derive(Clone)]
pub struct UserTokenInfo(pub Rc<UserToken>);

impl FromRequest for UserTokenInfo {
    type Error = Error;
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(
        req: &actix_web::HttpRequest,
        _payload: &mut actix_web::dev::Payload,
    ) -> Self::Future {
        let value = req.extensions().get::<Rc<UserToken>>().cloned();
        let result = match value {
            Some(v) => Ok(UserTokenInfo(v)),
            None => {
                Err(ServerResponseError(PackageServerError::KeycloakValidationFailed.into()).into())
            }
        };
        ready(result)
    }
}

impl std::ops::Deref for UserTokenInfo {
    type Target = Rc<UserToken>;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

pub struct LocalTokenAuthenticationMiddlewareFactory;

impl<S, B> Transform<S, ServiceRequest> for LocalTokenAuthenticationMiddlewareFactory
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error> + 'static,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type InitError = ();
    type Transform = LocalTokenAuhtenticationMiddleware<S>;
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ready(Ok(LocalTokenAuhtenticationMiddleware {
            service: Rc::new(service),
        }))
    }
}

pub struct LocalTokenAuhtenticationMiddleware<S> {
    service: Rc<S>,
}

impl<S, B> Service<ServiceRequest> for LocalTokenAuhtenticationMiddleware<S>
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
        let auth_header = req.headers().get("Authorization").cloned();
        let app_state = req.app_data::<Data<AppState<Database>>>().cloned();

        Box::pin(async move {
            let app_state = app_state.ok_or_else(|| {
                error!("App state not found");
                ServerResponseError(PackageServerError::AppStateMissing.into())
            })?;
            let token_string: HeaderValue = match auth_header {
                Some(value) => Ok(value),
                _ => Err(ServerResponseError(PackageServerError::TokenMissing.into())),
            }?;
            let token_string = token_string
                .to_str()
                .map_err(|e| {
                    error!("Failed to convert authorization header to string: {}", e);
                    ServerResponseError(PackageServerError::TokenMissing.into())
                })?
                .replace("Bearer ", "");
            let token_option = app_state
                .database_address
                .send(GetTokenByToken(token_string))
                .await
                .map_err(|error| {
                    error!("Mailbox error for getting tokens: {error}");
                    ServerResponseError(PackageServerError::MailboxError.into())
                })?
                .map_err(|error| {
                    error!("Database failed: {error}");
                    ServerResponseError(PackageServerError::DatabaseQueryFailed.into())
                })?
                .ok_or_else(|| {
                    error!("Token not found");
                    ServerResponseError(PackageServerError::TokenMissing.into())
                })?;

            req.extensions_mut()
                .insert::<Rc<UserToken>>(Rc::new(UserToken {
                    id: token_option.user_id,
                    email: token_option.email,
                }));

            let res = service.call(req).await?;
            Ok(res)
        })
    }
}
