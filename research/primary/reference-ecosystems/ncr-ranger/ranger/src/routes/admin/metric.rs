use crate::{
    constants::{ARTIFACT_EXTENSION_MIME_TYPE_WHITELIST, OCTET_STREAM_MIME_TYPE},
    errors::RangerError,
    middleware::{deployment::DeploymentInfo, metric::MetricInfo},
    models::{helpers::uuid::Uuid, metric::UpdateMetric, Metric},
    services::database::{
        metric::{DeleteMetric, GetMetrics},
        upload::GetArtifactByMetricId,
    },
    utilities::{create_database_error_handler, create_mailbox_error_handler, get_file_extension},
    AppState,
};
use actix_web::{
    delete, get,
    http::header::{ContentDisposition, DispositionParam, DispositionType},
    put,
    web::{Data, Json},
    HttpResponse,
};

#[put("")]
pub async fn update_admin_metric(
    app_state: Data<AppState>,
    metric_info: MetricInfo,
    update_metric: Json<UpdateMetric>,
) -> Result<Json<Metric>, RangerError> {
    let metric = metric_info.into_inner();
    let update_metric = update_metric.into_inner();

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
}

#[get("")]
pub async fn get_admin_metric(metric_info: MetricInfo) -> Result<Json<Metric>, RangerError> {
    Ok(Json(metric_info.into_inner()))
}

#[get("")]
pub async fn get_admin_metrics(
    app_state: Data<AppState>,
    deployment: DeploymentInfo,
) -> Result<Json<Vec<Metric>>, RangerError> {
    Ok(Json(
        app_state
            .database_address
            .send(GetMetrics(deployment.id))
            .await
            .map_err(create_mailbox_error_handler("Database"))?
            .map_err(create_database_error_handler("Get Manual Metrics"))?,
    ))
}

#[delete("")]
pub async fn delete_metric(
    app_state: Data<AppState>,
    metric_info: MetricInfo,
) -> Result<Json<Uuid>, RangerError> {
    let metric = metric_info.into_inner();
    app_state
        .database_address
        .send(DeleteMetric(metric.id, false))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Delete Manual Metric"))?;

    Ok(Json(metric.id))
}

#[get("/download")]
pub async fn download_metric_artifact(
    app_state: Data<AppState>,
    metric_info: MetricInfo,
) -> Result<HttpResponse, RangerError> {
    let artifact = app_state
        .database_address
        .send(GetArtifactByMetricId(metric_info.into_inner().id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get Metric Artifact"))?;

    let file_extension = get_file_extension(&artifact.name).unwrap_or_default();
    let content_type = ARTIFACT_EXTENSION_MIME_TYPE_WHITELIST
        .get(file_extension)
        .unwrap_or(&OCTET_STREAM_MIME_TYPE)
        .to_owned();

    Ok(HttpResponse::Ok()
        .content_type(content_type)
        .append_header(ContentDisposition {
            disposition: DispositionType::Attachment,
            parameters: vec![DispositionParam::Filename(artifact.name.to_owned())],
        })
        .body(artifact.content))
}
