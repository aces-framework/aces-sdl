use crate::{
    errors::RangerError,
    middleware::{authentication::UserInfo, deployment::DeploymentInfo},
    models::helpers::uuid::Uuid,
    services::database::participant::GetParticipants,
    utilities::{
        create_database_error_handler, create_mailbox_error_handler,
        scenario::filter_scenario_by_role, try_some,
    },
    AppState,
};
use actix_web::{
    get,
    web::{Data, Json, Path},
};
use anyhow::Result;
use log::error;
use sdl_parser::{entity::Flatten, parse_sdl, Scenario};

#[get("scenario/{entity_selector}")]
pub async fn get_participant_exercise_deployment_scenario(
    app_state: Data<AppState>,
    user_details: UserInfo,
    deployment: DeploymentInfo,
    path_variables: Path<(Uuid, Uuid, String)>,
) -> Result<Json<Scenario>, RangerError> {
    let (_exercise_uuid, _deployment_uuid, entity_selector) = path_variables.into_inner();
    let scenario = parse_sdl(&deployment.sdl_schema).map_err(|error| {
        error!("Failed to parse sdl: {error}");
        RangerError::ScenarioParsingFailed
    })?;
    let entities =
        try_some(scenario.entities.clone(), "Scenario missing Entities").map_err(|error| {
            error!("{error}");
            RangerError::EntityNotFound
        })?;
    let participants = app_state
        .database_address
        .send(GetParticipants(deployment.id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get participants"))?;

    let valid_participant_entity_selectors: Vec<String> = participants
        .into_iter()
        .filter_map(
            |participant| match participant.user_id.eq(&user_details.id) {
                true => Some(participant.selector.replace("entities.", "")),
                false => None,
            },
        )
        .collect();

    if valid_participant_entity_selectors.contains(&entity_selector) {
        let flattened_entities = entities.flatten();
        let participant_entity = match flattened_entities.get(&entity_selector) {
            Some(participant_entity) => participant_entity,
            None => return Err(RangerError::EntityNotFound),
        };

        let participant_role = try_some(participant_entity.role.clone(), "Entity missing role")
            .map_err(|error| {
                error!("{error}");
                RangerError::ScenarioParsingFailed
            })?;

        let participant_scenario = filter_scenario_by_role(&scenario, participant_role);
        Ok(Json(participant_scenario))
    } else {
        error!("Requested Entity is not among the Participants Entities");
        Err(RangerError::NotAuthorized)
    }
}
