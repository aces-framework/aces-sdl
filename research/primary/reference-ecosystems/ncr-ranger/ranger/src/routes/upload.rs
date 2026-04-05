use crate::{
    constants::{ARTIFACT_EXTENSION_MIME_TYPE_WHITELIST, MAX_ARTIFACT_FILE_SIZE},
    errors::RangerError,
    middleware::metric::MetricInfo,
    models::upload::NewArtifact,
    services::database::{metric::GetMetric, upload::UploadArtifact},
    utilities::{create_database_error_handler, create_mailbox_error_handler, get_file_extension},
    AppState,
};
use actix_multipart::Multipart;
use actix_web::{http::header::CONTENT_LENGTH, post, web::Data, HttpRequest};
use futures_util::{StreamExt, TryStreamExt};
use log::error;

#[post("/upload")]
pub async fn upload_participant_artifact(
    app_state: Data<AppState>,
    metric_info: MetricInfo,
    mut payload: Multipart,
    req: HttpRequest,
) -> Result<String, RangerError> {
    let metric_id = metric_info.into_inner().id;

    let metric = app_state
        .database_address
        .send(GetMetric(metric_id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get metric"))?;

    if metric.score.is_some() {
        return Err(RangerError::MetricAlreadyScored);
    };
    let content_length: usize = match req.headers().get(CONTENT_LENGTH) {
        Some(length) => match length.to_str() {
            Ok(length) => match length.parse::<usize>() {
                Ok(length) => length,
                Err(_) => return Err(RangerError::FileUploadFailed),
            },
            Err(_) => return Err(RangerError::FileUploadFailed),
        },
        None => return Err(RangerError::FileUploadFailed),
    };

    if content_length > MAX_ARTIFACT_FILE_SIZE {
        return Err(RangerError::PayloadTooLarge);
    }

    if let Ok(Some(mut field)) = payload.try_next().await {
        let content_disposition = &field.content_disposition().clone();

        if let Some(filename) = content_disposition.get_filename() {
            let mut artifact_buffer = Vec::new();
            if ARTIFACT_EXTENSION_MIME_TYPE_WHITELIST
                .contains_key(get_file_extension(filename).unwrap_or_default())
            {
                while let Some(chunk) = field.next().await {
                    let data = chunk.map_err(|_| RangerError::FileUploadFailed)?;
                    artifact_buffer.extend_from_slice(&data);
                }
            } else {
                return Err(RangerError::UnsupportedMediaType);
            }

            let new_artifact = NewArtifact::new(metric_id, filename.to_owned(), artifact_buffer);

            let artifact_uuid = app_state
                .database_address
                .send(UploadArtifact(new_artifact))
                .await
                .map_err(create_mailbox_error_handler("Database"))?
                .map_err(create_database_error_handler("Upload file"))?;
            return Ok(artifact_uuid.0.to_string());
        }
        Err(RangerError::FileUploadFailed)
    } else {
        error!("No file found Artifact request");
        Err(RangerError::FileUploadFailed)
    }
}
