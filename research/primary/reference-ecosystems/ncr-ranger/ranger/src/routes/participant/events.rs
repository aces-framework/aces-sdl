use crate::{
    errors::RangerError,
    middleware::deployment::DeploymentInfo,
    models::{helpers::uuid::Uuid, Event},
    services::database::event::GetEventsByDeploymentId,
    utilities::{
        create_database_error_handler, create_mailbox_error_handler,
        scenario::inherit_parent_events,
    },
    AppState,
};
use actix_web::{
    get,
    web::{Data, Json, Path},
};
use anyhow::Result;
use log::error;
use sdl_parser::{
    entity::{Entities, Flatten},
    parse_sdl,
};
use std::collections::HashMap;

#[get("")]
pub async fn get_participant_events(
    app_state: Data<AppState>,
    deployment: DeploymentInfo,
    path_variables: Path<(Uuid, Uuid, String)>,
) -> Result<Json<Vec<Event>>, RangerError> {
    let (_exercise_uuid, deployment_uuid, entity_selector) = path_variables.into_inner();
    let scenario = parse_sdl(&deployment.sdl_schema).map_err(|error| {
        error!("Failed to parse sdl: {error}");
        RangerError::ScenarioParsingFailed
    })?;

    let deployment_events = app_state
        .database_address
        .send(GetEventsByDeploymentId(deployment_uuid))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get events"))?;

    let flattened_entities: Entities = scenario
        .entities
        .as_ref()
        .unwrap_or(&HashMap::new())
        .flatten();

    let entities_with_parent_events = inherit_parent_events(&flattened_entities);

    let entity_events =
        deployment_events
            .into_iter()
            .fold(vec![], |mut entity_events, deployment_event| {
                if let Some(entity) = entities_with_parent_events.get(&entity_selector) {
                    if let Some(entity_event_keys) = &entity.events {
                        entity_event_keys.iter().for_each(|event_key| {
                            if deployment_event.name.eq(event_key)
                                && !entity_events.contains(&deployment_event)
                            {
                                entity_events.push(deployment_event.clone());
                            }
                        })
                    }
                }

                entity_events
            });

    let triggered_entity_events = entity_events
        .into_iter()
        .filter(|event| event.has_triggered)
        .collect::<Vec<_>>();

    Ok(Json(triggered_entity_events))
}
