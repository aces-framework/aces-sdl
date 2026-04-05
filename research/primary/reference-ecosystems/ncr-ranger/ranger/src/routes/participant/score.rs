use crate::{
    errors::RangerError,
    middleware::deployment::DeploymentInfo,
    models::{helpers::uuid::Uuid, Score},
    services::database::{
        condition::GetConditionMessagesByDeploymentId,
        deployment::GetDeploymentElementByDeploymentId, metric::GetMetrics,
    },
    utilities::{
        create_database_error_handler, create_mailbox_error_handler,
        scenario::{filter_scenario_by_role, get_role_from_string},
        try_some,
    },
    AppState,
};
use actix_web::{
    get,
    web::{Data, Json, Path},
};
use anyhow::Result;
use bigdecimal::BigDecimal;
use log::error;
use ranger_grpc::capabilities::DeployerType as GrpcDeployerType;
use sdl_parser::{entity::Flatten, parse_sdl};
use std::collections::HashMap;

#[get("")]
pub async fn get_participant_exercise_deployment_scores(
    path_variables: Path<(Uuid, Uuid, String)>,
    app_state: Data<AppState>,
    deployment: DeploymentInfo,
) -> Result<Json<Vec<Score>>, RangerError> {
    let (_exercise_uuid, deployment_uuid, entity_selector) = path_variables.into_inner();
    let scenario = parse_sdl(&deployment.sdl_schema).map_err(|error| {
        error!("Failed to parse sdl: {error}");
        RangerError::ScenarioParsingFailed
    })?;
    let entities = scenario.entities.clone().ok_or_else(|| {
        error!("Scenario missing Entities");
        RangerError::EntityNotFound
    })?;
    let flattened_entities = entities.flatten();

    let participant_entity = match flattened_entities.get(&entity_selector) {
        Some(participant_entity) => participant_entity,
        None => return Err(RangerError::EntityNotFound),
    };

    let participant_role = participant_entity.role.clone().ok_or_else(|| {
        error!("Entity missing role");
        RangerError::EntityNotFound
    })?;

    let participant_scenario = filter_scenario_by_role(&scenario, participant_role.clone());
    let scenario_metrics = match participant_scenario.metrics {
        Some(metrics) => metrics,
        None => return Ok(Json(vec![])),
    };

    let participant_node_keys: Vec<String> = participant_scenario
        .nodes
        .into_iter()
        .flat_map(|nodes| nodes.into_keys())
        .collect();

    let deployment_elements = app_state
        .database_address
        .send(GetDeploymentElementByDeploymentId(deployment_uuid, false))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get deployment elements"))?;

    let vm_scenario_refs_by_id = deployment_elements
        .iter()
        .filter(|element| {
            matches!(element.deployer_type.0, GrpcDeployerType::VirtualMachine)
                && element.handler_reference.is_some()
                && participant_node_keys.contains(&element.scenario_reference)
        })
        .map(|element| {
            let vm_id = try_some(
                element.handler_reference.to_owned(),
                "VM element missing handler reference",
            )?;
            Ok((vm_id, element.scenario_reference.to_owned()))
        })
        .collect::<Result<HashMap<String, String>>>()
        .map_err(create_database_error_handler("Get deployment elements"))?;

    let mut condition_messages = app_state
        .database_address
        .send(GetConditionMessagesByDeploymentId(deployment_uuid))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get condition messages"))?;
    condition_messages.retain(|condition| {
        condition.created_at > deployment.start
            && condition.created_at < deployment.end
            && vm_scenario_refs_by_id.contains_key(&condition.virtual_machine_id.to_string())
    });

    let manual_metrics = app_state
        .database_address
        .send(GetMetrics(deployment.id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get Manual Metrics"))?;

    let mut scores: Vec<Score> = manual_metrics
        .iter()
        .filter(|metric| get_role_from_string(&metric.role) == Some(participant_role.clone()))
        .cloned()
        .map(Into::into)
        .collect();

    for condition_message in condition_messages {
        if let Some((metric_key, metric)) = scenario_metrics
            .iter()
            .find(|(_, metric)| metric.condition == Some(condition_message.condition_name.clone()))
        {
            if let Some(vm_scenario_reference) =
                vm_scenario_refs_by_id.get(&condition_message.virtual_machine_id.to_string())
            {
                scores.push(Score::new(
                    condition_message.exercise_id,
                    condition_message.deployment_id,
                    metric.name.clone(),
                    metric_key.to_owned(),
                    vm_scenario_reference.to_owned(),
                    condition_message.value * BigDecimal::from(metric.max_score),
                    condition_message.created_at,
                ));
            }
        }
    }

    Ok(Json(scores))
}
