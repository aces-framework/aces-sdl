use crate::{
    errors::{PackageServerError, ServerResponseError},
    middleware::authentication::local_token::UserToken,
    services::database::{owner::GetOwners, Database},
    AppState,
};
use actix_http::HttpMessage;
use actix_web::{
    dev::{forward_ready, Service, ServiceRequest, ServiceResponse, Transform},
    web::Data,
    Error,
};
use futures_util::future::LocalBoxFuture;
use log::error;
use std::{
    future::{ready, Ready},
    rc::Rc,
};

pub struct OwnerAuthenticationMiddlewareFactory;

impl<S, B> Transform<S, ServiceRequest> for OwnerAuthenticationMiddlewareFactory
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error> + 'static,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type InitError = ();
    type Transform = OwnerAuthenticationMiddleware<S>;
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ready(Ok(OwnerAuthenticationMiddleware {
            service: Rc::new(service),
        }))
    }
}

pub struct OwnerAuthenticationMiddleware<S> {
    service: Rc<S>,
}

impl<S, B> Service<ServiceRequest> for OwnerAuthenticationMiddleware<S>
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
        let app_state = req.app_data::<Data<AppState<Database>>>().cloned();

        Box::pin(async move {
            let app_state = app_state.ok_or_else(|| {
                error!("App state not found");
                ServerResponseError(PackageServerError::AppStateMissing.into())
            })?;
            let package_name = req
                .match_info()
                .get("package_name")
                .ok_or_else(|| error!("Package name not found"))
                .map_err(|_| ServerResponseError(PackageServerError::PathParameters.into()))?;
            let owners = app_state
                .database_address
                .send(GetOwners(package_name.to_owned()))
                .await
                .map_err(|_| ServerResponseError(PackageServerError::OwnersList.into()))?
                .map_err(|_| ServerResponseError(PackageServerError::DatabaseQueryFailed.into()))?;
            let requester_email = req
                .extensions()
                .get::<Rc<UserToken>>()
                .ok_or_else(|| error!("Requester token not found"))
                .map_err(|_| ServerResponseError(PackageServerError::TokenMissing.into()))?
                .email
                .clone();

            if owners.contains_email(&requester_email) {
                let res = service.call(req).await?;
                Ok(res)
            } else {
                Err(ServerResponseError(PackageServerError::NotAuthorized.into()).into())
            }
        })
    }
}
