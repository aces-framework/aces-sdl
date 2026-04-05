use crate::{
    errors::RangerError,
    middleware::{authentication::UserInfo, deployment::DeploymentInfo},
    models::Participant,
    services::database::participant::GetParticipants,
    utilities::{create_database_error_handler, create_mailbox_error_handler},
    AppState,
};
use actix_web::{
    get,
    web::{Data, Json},
};
use anyhow::Result;

#[get("participant")]
pub async fn get_own_participants(
    app_state: Data<AppState>,
    user_details: UserInfo,
    deployment: DeploymentInfo,
) -> Result<Json<Vec<Participant>>, RangerError> {
    let participants = app_state
        .database_address
        .send(GetParticipants(deployment.id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get participants"))?;

    let requester_participants: Vec<Participant> = participants
        .into_iter()
        .filter_map(
            |participant| match participant.user_id.eq(&user_details.id) {
                true => Some(participant),
                false => None,
            },
        )
        .collect();

    Ok(Json(requester_participants))
}
