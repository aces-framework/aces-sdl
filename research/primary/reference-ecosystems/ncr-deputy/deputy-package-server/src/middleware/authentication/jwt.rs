use crate::{
    constants::JWT_AUDIENCE,
    errors::{PackageServerError, ServerResponseError},
};
use actix_http::HttpMessage;
use actix_web::{
    dev::{forward_ready, Service, ServiceRequest, ServiceResponse, Transform},
    error::ErrorUnauthorized,
    http::header::HeaderValue,
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
    pub realm_access: Option<RealmAccess>,
    pub exp: u64,
    pub name: Option<String>,
    pub email: Option<String>,
    pub typ: Option<String>,
}

impl Token {
    pub async fn try_new(token: &str, pem: &str) -> Result<Self, Error> {
        let pem_file = format!(
            "-----BEGIN PUBLIC KEY-----
    {pem}
    -----END PUBLIC KEY-----"
        );
        let decoding_key = DecodingKey::from_rsa_pem(pem_file.as_bytes()).map_err(|e| {
            error!("Failed to create decoding key: {}", e);
            ErrorUnauthorized("Invalid decoding key")
        })?;

        let mut validation = Validation::new(Algorithm::RS256);
        validation.set_audience(&[JWT_AUDIENCE]);

        let decoded_token = jsonwebtoken::decode::<Token>(token, &decoding_key, &validation)
            .map_err(|e| {
                error!("Failed to decode JWT: {}", e);
                ErrorUnauthorized("Invalid token")
            })?;

        if decoded_token.claims.typ.as_deref() != Some("Bearer") {
            error!("Invalid token type: {:?}", decoded_token.claims.typ);
            return Err(ErrorUnauthorized("Invalid token type"));
        }

        Ok(decoded_token.claims)
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct User {
    pub id: String,
    pub name: Option<String>,
    pub email: Option<String>,
}

impl From<Token> for User {
    fn from(token: Token) -> Self {
        Self {
            id: token.sub,
            name: token.name,
            email: token.email,
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
            None => {
                Err(ServerResponseError(PackageServerError::KeycloakValidationFailed.into()).into())
            }
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

pub struct AuthenticationMiddlewareFactory(pub String);

impl<S, B> Transform<S, ServiceRequest> for AuthenticationMiddlewareFactory
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error> + 'static,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type InitError = ();
    type Transform = AuhtenticationMiddleware<S>;
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ready(Ok(AuhtenticationMiddleware {
            service: Rc::new(service),
            pem_content: self.0.clone(),
        }))
    }
}

pub struct AuhtenticationMiddleware<S> {
    service: Rc<S>,
    pem_content: String,
}

impl<S, B> Service<ServiceRequest> for AuhtenticationMiddleware<S>
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
        let pem_content = self.pem_content.clone();
        let auth_header = req.headers().get("Authorization").cloned();

        Box::pin(async move {
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
            let token = Token::try_new(token_string.as_str(), &pem_content).await?;

            req.extensions_mut()
                .insert::<Rc<User>>(Rc::new(User::from(token)));

            let res = service.call(req).await?;
            Ok(res)
        })
    }
}
