use std::{
    future::{ready, Ready},
    rc::Rc,
};

use crate::{configuration::KeycloakConfiguration, errors::RangerError, AppState};
use actix_http::HttpMessage;
use actix_web::{
    dev::{forward_ready, Service, ServiceRequest, ServiceResponse, Transform},
    web::Data,
    Error, FromRequest,
};
use futures_util::future::LocalBoxFuture;
use keycloak::{KeycloakAdmin, KeycloakServiceAccountAdminTokenRetriever};
use log::error;

pub struct KeycloakAccess {
    pub service_user: KeycloakAdmin<KeycloakServiceAccountAdminTokenRetriever>,
    pub client_id: String,
}

pub struct KeycloakInfo(pub Rc<KeycloakAccess>);

impl FromRequest for KeycloakInfo {
    type Error = Error;
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(
        req: &actix_web::HttpRequest,
        _payload: &mut actix_web::dev::Payload,
    ) -> Self::Future {
        let value = req.extensions().get::<Rc<KeycloakAccess>>().cloned();
        let result = match value {
            Some(v) => Ok(KeycloakInfo(v)),
            None => Err(RangerError::KeycloakQueryFailed.into()),
        };
        ready(result)
    }
}

impl std::ops::Deref for KeycloakInfo {
    type Target = Rc<KeycloakAccess>;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

impl KeycloakAccess {
    pub async fn try_new(
        keycloak_configuration: &KeycloakConfiguration,
    ) -> Result<Self, RangerError> {
        let client = reqwest::Client::new();
        let token = KeycloakServiceAccountAdminTokenRetriever::create_with_custom_realm(
            &keycloak_configuration.client_id,
            &keycloak_configuration.client_secret,
            &keycloak_configuration.realm,
            client,
        );
        let client = reqwest::Client::new();
        let service_user = KeycloakAdmin::new(&keycloak_configuration.base_url, token, client);
        let keycloak_clients = service_user
            .realm_clients_get(
                &keycloak_configuration.realm,
                Some(keycloak_configuration.client_id.clone()),
                None,
                None,
                None,
                None,
                None,
            )
            .await
            .map_err(|error| {
                error!("Failed to get keycloak clients: {error}");
                RangerError::KeycloakQueryFailed
            })?;

        let keycloak_client_id = keycloak_clients
            .first()
            .ok_or_else(|| {
                error!("Failed to get keycloak client");
                RangerError::KeycloakQueryFailed
            })?
            .clone()
            .id
            .ok_or_else(|| {
                error!("Failed to get keycloak client id");
                RangerError::KeycloakQueryFailed
            })?;
        Ok(Self {
            client_id: keycloak_client_id,
            service_user,
        })
    }
}

pub struct KeycloakAccessMiddlewareFactory;

impl<S, B> Transform<S, ServiceRequest> for KeycloakAccessMiddlewareFactory
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error> + 'static,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type Transform = KeycloakAccessMiddleware<S>;
    type InitError = ();
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ready(Ok(KeycloakAccessMiddleware {
            service: Rc::new(service),
        }))
    }
}

pub struct KeycloakAccessMiddleware<S> {
    service: Rc<S>,
}

impl<S, B> Service<ServiceRequest> for KeycloakAccessMiddleware<S>
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
            let keycloak_configuration = app_state
                .ok_or_else(|| {
                    error!("Keycloak configuration not found");
                    RangerError::KeycloakQueryFailed
                })?
                .configuration
                .keycloak
                .clone();
            let keycloak_access = KeycloakAccess::try_new(&keycloak_configuration).await?;
            req.extensions_mut()
                .insert::<Rc<KeycloakAccess>>(Rc::new(keycloak_access));

            let res = service.call(req).await?;
            Ok(res)
        })
    }
}
