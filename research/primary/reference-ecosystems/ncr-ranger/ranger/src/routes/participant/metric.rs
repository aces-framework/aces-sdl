use crate::{
    errors::RangerError,
    middleware::{deployment::DeploymentInfo, metric::MetricInfo},
    models::{
        helpers::uuid::Uuid,
        metric::{NewMetric, NewMetricResource},
        Metric, UpdateMetric,
    },
    services::database::metric::{CreateMetric, GetMetrics},
    utilities::{create_database_error_handler, create_mailbox_error_handler},
    AppState,
};
use actix_web::{
    get, post, put,
    web::{Data, Json, Path},
};
use log::error;
use sdl_parser::Scenario;

#[get("")]
pub async fn get_participant_metric(
    metric_info: MetricInfo,
    path_variables: Path<(Uuid, Uuid, String)>,
) -> Result<Json<Metric>, RangerError> {
    let metric = metric_info.into_inner();
    let (_exercise_uuid, _deployment_uuid, entity_selector) = path_variables.into_inner();
    if metric.entity_selector.eq(&entity_selector) {
        Ok(Json(metric))
    } else {
        Err(RangerError::NotAuthorized)
    }
}

#[get("")]
pub async fn get_participant_metrics(
    app_state: Data<AppState>,
    path_variables: Path<(Uuid, Uuid, String)>,
    deployment: DeploymentInfo,
) -> Result<Json<Vec<Metric>>, RangerError> {
    let (_exercise_uuid, _deployment_uuid, entity_selector) = path_variables.into_inner();
    let metrics = app_state
        .database_address
        .send(GetMetrics(deployment.id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get Manual Metrics"))?;
    let users_metrics = metrics
        .into_iter()
        .filter(|metric| metric.entity_selector.eq(&entity_selector))
        .collect();

    Ok(Json(users_metrics))
}

#[put("")]
pub async fn update_participant_metric(
    app_state: Data<AppState>,
    metric_info: MetricInfo,
    path_variables: Path<(Uuid, Uuid, String)>,
    update_metric: Json<UpdateMetric>,
) -> Result<Json<Metric>, RangerError> {
    let metric = metric_info.into_inner();
    let update_metric = update_metric.into_inner();
    let (_exercise_uuid, _deployment_uuid, entity_selector) = path_variables.into_inner();

    if metric.score.is_some() {
        return Err(RangerError::MetricAlreadyScored);
    };
    if metric.entity_selector.eq(&entity_selector) || update_metric.score.is_some() {
        let metric = app_state
            .database_address
            .send(crate::services::database::metric::UpdateMetric(
                metric.id,
                update_metric,
            ))
            .await
            .map_err(create_mailbox_error_handler("Deployment"))?
            .map_err(create_database_error_handler("Create deployment"))?;
        Ok(Json(metric))
    } else {
        Err(RangerError::NotAuthorized)
    }
}

#[post("")]
pub async fn add_metric(
    app_state: Data<AppState>,
    deployment: DeploymentInfo,
    new_metric: Json<NewMetricResource>,
) -> Result<Json<Uuid>, RangerError> {
    let deployment = deployment.into_inner();
    let scenario = Scenario::from_yaml(&deployment.sdl_schema).map_err(|error| {
        error!("Deployment error: {error}");
        RangerError::DeploymentFailed
    })?;

    let new_metric_resource = new_metric.into_inner();
    if let Some(metrics) = scenario.metrics {
        let metric = match metrics.get(&new_metric_resource.metric_key) {
            Some(metric) => metric,
            None => {
                error!(
                    "Metric '{}' not found in Scenario",
                    &new_metric_resource.metric_key
                );
                return Err(RangerError::MetricNotFound);
            }
        };

        let new_metric = NewMetric::new(
            metric.name.clone(),
            metric.description.clone(),
            metric.max_score,
            new_metric_resource,
        );

        let metric = app_state
            .database_address
            .send(CreateMetric(new_metric))
            .await
            .map_err(create_mailbox_error_handler("Deployment"))?
            .map_err(create_database_error_handler("Create deployment"))?;

        Ok(Json(metric.id))
    } else {
        error!("Scenario has no Metrics");
        Err(RangerError::MetricNotFound)
    }
}
