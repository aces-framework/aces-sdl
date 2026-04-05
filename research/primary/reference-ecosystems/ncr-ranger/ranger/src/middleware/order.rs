use crate::{
    errors::RangerError,
    middleware::authentication::User,
    models::{helpers::uuid::Uuid, Order},
    roles::RangerRole,
    services::database::order::GetOrder,
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

pub struct OrderInfo(pub Order);

impl OrderInfo {
    pub fn into_inner(self) -> Order {
        self.0
    }
}

impl FromRequest for OrderInfo {
    type Error = Error;
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(
        req: &actix_web::HttpRequest,
        _payload: &mut actix_web::dev::Payload,
    ) -> Self::Future {
        let value = req.extensions().get::<Order>().cloned();
        let result = match value {
            Some(v) => Ok(OrderInfo(v)),
            None => Err(RangerError::KeycloakQueryFailed.into()),
        };
        ready(result)
    }
}

impl std::ops::Deref for OrderInfo {
    type Target = Order;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

pub struct OrderMiddlewareFactory;

impl<S, B> Transform<S, ServiceRequest> for OrderMiddlewareFactory
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error> + 'static,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type Transform = OrderMiddleware<S>;
    type InitError = ();
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ready(Ok(OrderMiddleware {
            service: Rc::new(service),
        }))
    }
}

pub struct OrderMiddleware<S> {
    service: Rc<S>,
}

impl<S, B> Service<ServiceRequest> for OrderMiddleware<S>
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
        debug!("Order middleware called");
        let service = self.service.clone();
        let user = req.extensions().get::<Rc<User>>().cloned();
        let app_state: Option<Data<AppState>> = req.app_data::<Data<AppState>>().cloned();

        Box::pin(async move {
            let user = user.ok_or_else(|| {
                error!("User not found");
                RangerError::UserInfoMissing
            })?;
            let app_state = app_state.ok_or_else(|| {
                error!("App state not found");
                RangerError::AppStateMissing
            })?;
            let order_uuid =
                Uuid::try_from(req.match_info().get("order_uuid").ok_or_else(|| {
                    error!("Order uuid not found");
                    RangerError::UuidParsingFailed
                })?)
                .map_err(|_| {
                    error!("Invalid order uuid");
                    RangerError::UuidParsingFailed
                })?;

            let order = app_state
                .database_address
                .send(GetOrder(order_uuid))
                .await
                .map_err(create_mailbox_error_handler("Database"))?
                .map_err(create_database_error_handler("Get order"))?;

            let order = match user.role {
                RangerRole::Admin => std::result::Result::Ok::<Order, Self::Error>(order),
                RangerRole::Participant => {
                    return Err(RangerError::AccessForbidden.into());
                }
                RangerRole::Client => {
                    if let Some(client_id) = &user.email {
                        if order.is_owner(client_id) {
                            std::result::Result::Ok::<Order, Self::Error>(order)
                        } else {
                            return Err(RangerError::OrderNotFound.into());
                        }
                    } else {
                        return Err(RangerError::OrderNotFound.into());
                    }
                }
            }?;
            req.extensions_mut().insert(order);

            let res = service.call(req).await?;
            Ok(res)
        })
    }
}
