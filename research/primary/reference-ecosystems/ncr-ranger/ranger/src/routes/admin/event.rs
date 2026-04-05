use crate::{
    errors::RangerError,
    middleware::deployment::DeploymentInfo,
    models::{event_info::EventInfo, helpers::uuid::Uuid, Event},
    services::database::{event::GetEventsByDeploymentId, event_info::GetEventInfo},
    utilities::{create_database_error_handler, create_mailbox_error_handler},
    AppState,
};
use actix_web::{
    get,
    web::{Data, Json, Path},
};
use anyhow::Result;

#[get("")]
pub async fn get_exercise_deployment_events(
    path_variables: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
) -> Result<Json<Vec<Event>>, RangerError> {
    let (_exercise_uuid, deployment_uuid) = path_variables.into_inner();

    let deployment_events = app_state
        .database_address
        .send(GetEventsByDeploymentId(deployment_uuid))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get events"))?;

    Ok(Json(deployment_events))
}

#[get("")]
pub async fn get_admin_event_info_data(
    app_state: Data<AppState>,
    _deployment: DeploymentInfo,
    path_variables: Path<(Uuid, Uuid, String)>,
) -> Result<Json<EventInfo>, RangerError> {
    let (_exercise_uuid, _deployment_uuid, event_info_checksum) = path_variables.into_inner();

    let event = app_state
        .database_address
        .send(GetEventInfo(event_info_checksum, false))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get Event Info"))?;

    Ok(Json(event))
}
