use crate::{
    errors::RangerError,
    models::{helpers::uuid::Uuid, metric::Metric},
    services::database::metric::GetMetric,
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
use log::error;
use std::{
    future::{ready, Ready},
    rc::Rc,
};

#[derive(Clone, Debug)]
pub struct MetricInfo(pub Metric);

impl MetricInfo {
    pub fn into_inner(self) -> Metric {
        self.0
    }
}

impl FromRequest for MetricInfo {
    type Error = Error;
    type Future = Ready<Result<Self, Self::Error>>;

    fn from_request(
        req: &actix_web::HttpRequest,
        _payload: &mut actix_web::dev::Payload,
    ) -> Self::Future {
        let value = req.extensions().get::<MetricInfo>().cloned();
        let result = match value {
            Some(v) => Ok(MetricInfo(v.0)),
            None => Err(RangerError::KeycloakQueryFailed.into()),
        };
        ready(result)
    }
}

impl std::ops::Deref for MetricInfo {
    type Target = Metric;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

pub struct MetricMiddlewareFactory;

impl<S, B> Transform<S, ServiceRequest> for MetricMiddlewareFactory
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error> + 'static,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<B>;
    type Error = Error;
    type Transform = MetricMiddleware<S>;
    type InitError = ();
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ready(Ok(MetricMiddleware {
            service: Rc::new(service),
        }))
    }
}

pub struct MetricMiddleware<S> {
    service: Rc<S>,
}

impl<S, B> Service<ServiceRequest> for MetricMiddleware<S>
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

            let metric_uuid =
                Uuid::try_from(req.match_info().get("metric_uuid").ok_or_else(|| {
                    error!("Metric uuid path param not found");
                    RangerError::UuidParsingFailed
                })?)
                .map_err(|_| {
                    error!("Invalid Metric uuid");
                    RangerError::UuidParsingFailed
                })?;

            let manual_metric = app_state
                .database_address
                .send(GetMetric(metric_uuid))
                .await
                .map_err(create_mailbox_error_handler("Database"))?
                .map_err(create_database_error_handler("Get Metric"))?;

            req.extensions_mut().insert(MetricInfo(manual_metric));

            let res = service.call(req).await?;
            Ok(res)
        })
    }
}
