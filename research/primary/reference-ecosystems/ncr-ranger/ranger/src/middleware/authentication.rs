use crate::{errors::RangerError, roles::RangerRole, AppState};
use actix_http::HttpMessage;
use actix_web::{
    dev::{forward_ready, Service, ServiceRequest, ServiceResponse, Transform},
    error::ErrorUnauthorized,
    http::header::HeaderValue,
    web::Data,
    Error, FromRequest,
};
use futures_util::future::LocalBoxFuture;
use jsonwebtoken::{Algorithm, DecodingKey, Validation};
use log::error;
use serde::{Deserialize, Serialize};
use std::{
    future::{ready, Ready},
    rc::Rc,
};

#[derive(Debug, Serialize, Deserialize)]
pub struct RealmAccess {
    roles: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Token {
    pub sub: String,
    pub realm_access: RealmAccess,
    pub exp: u64,
    pub name: Option<String>,
    pub email: Option<String>,
}

impl Token {
    pub async fn try_new(token: &str, pem: &str) -> Result<Self, Error> {
        let pem_file = format!(
            "-----BEGIN PUBLIC KEY-----
    {pem}
    -----END PUBLIC KEY-----"
        );
        let decoding_key = DecodingKey::from_rsa_pem(pem_file.as_bytes()).unwrap();
        jsonwebtoken::decode::<Token>(token, &decoding_key, &Validation::new(Algorithm::RS256))
            .map(|data| data.claims)
            .map_err(|e| {
                log::error!("Failed to decode JWT: {}", e);
                ErrorUnauthorized(e.to_string())
            })
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct User {
    pub id: String,
    pub name: Option<String>,
    pub email: Option<String>,
    pub role: RangerRole,
}

impl From<(Token, RangerRole)> for User {
    fn from((token, ranger_role): (Token, RangerRole)) -> Self {
        Self {
            id: token.sub,
            name: token.name,
            email: token.email,
            role: ranger_role,
        }
    }
}

#[derive(Clone)]
pub struct UserInfo(pub Rc<User>);

impl FromRequest for UserInfo {
    type Error = Error;
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(
        req: &actix_web::HttpRequest,
        _payload: &mut actix_web::dev::Payload,
    ) -> Self::Future {
        let value = req.extensions().get::<Rc<User>>().cloned();
        let result = match value {
            Some(v) => Ok(UserInfo(v)),
            None => Err(RangerError::KeycloakQueryFailed.into()),
        };
        ready(result)
    }
}

impl std::ops::Deref for UserInfo {
    type Target = Rc<User>;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

pub struct AuthenticationMiddlewareFactory(pub RangerRole);

impl<S, B> Transform<S, ServiceRequest> for AuthenticationMiddlewareFactory
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error> + 'static,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type Transform = AuthenticationMiddleware<S>;
    type InitError = ();
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ready(Ok(AuthenticationMiddleware {
            service: Rc::new(service),
            expected_role: self.0,
        }))
    }
}

pub struct AuthenticationMiddleware<S> {
    service: Rc<S>,
    expected_role: RangerRole,
}

impl<S, B> Service<ServiceRequest> for AuthenticationMiddleware<S>
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
        let expected_role = self.expected_role;
        let app_state = req.app_data::<Data<AppState>>().cloned();
        let auth_header = req.headers().get("Authorization").cloned();
        let auth_header_ws = req.headers().get("Sec-WebSocket-Protocol").cloned();

        Box::pin(async move {
            let keycloak_configuration = app_state
                .ok_or_else(|| {
                    error!("Keycloak configuration not found");
                    RangerError::ConfigurationMissing
                })?
                .configuration
                .keycloak
                .clone();
            let token_string: HeaderValue = match auth_header {
                Some(value) => Ok(value),
                _ => match auth_header_ws.clone() {
                    Some(value) => Ok(value),
                    _ => Err(RangerError::TokenMissing),
                },
            }?;
            let token_string = token_string
                .to_str()
                .map_err(|e| {
                    error!("Failed to convert authorization header to string: {}", e);
                    RangerError::TokenMissing
                })?
                .replace("Bearer ", "");
            let token = Token::try_new(
                token_string.as_str(),
                &keycloak_configuration.authentication_pem_content,
            )
            .await?;

            if !token
                .realm_access
                .roles
                .contains(&expected_role.to_string())
            {
                error!("User does not have required role");
                return Err(RangerError::AccessForbidden.into());
            }

            req.extensions_mut()
                .insert::<Rc<User>>(Rc::new(User::from((token, expected_role))));

            let res = service.call(req).await?;
            Ok(res)
        })
    }
}
