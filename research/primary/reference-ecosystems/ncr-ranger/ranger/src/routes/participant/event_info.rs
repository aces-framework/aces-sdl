use crate::{
    errors::RangerError,
    middleware::deployment::DeploymentInfo,
    models::{event_info::EventInfo, helpers::uuid::Uuid},
    services::database::event_info::GetEventInfo,
    utilities::{create_database_error_handler, create_mailbox_error_handler},
    AppState,
};
use actix_web::{
    get,
    web::{Data, Json, Path},
};
use anyhow::Result;

#[get("")]
pub async fn get_participant_event_info_data(
    app_state: Data<AppState>,
    _deployment: DeploymentInfo,
    path_variables: Path<(Uuid, Uuid, String, String)>,
) -> Result<Json<EventInfo>, RangerError> {
    let (_exercise_uuid, _deployment_uuid, _entity_selector, event_info_checksum) =
        path_variables.into_inner();

    let event = app_state
        .database_address
        .send(GetEventInfo(event_info_checksum, false))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get Event Info"))?;

    Ok(Json(event))
}
