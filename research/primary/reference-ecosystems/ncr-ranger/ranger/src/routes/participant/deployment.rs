use crate::{
    errors::RangerError,
    middleware::{
        authentication::UserInfo, deployment::DeploymentInfo, exercise::ExerciseInfo,
        keycloak::KeycloakInfo,
    },
    models::{helpers::uuid::Uuid, DeploymentElement, ParticipantDeployment},
    services::database::deployment::{GetDeploymentElementByDeploymentId, GetDeployments},
    services::websocket::ExerciseWebsocket,
    utilities::{create_database_error_handler, create_mailbox_error_handler},
    AppState,
};
use actix_web::{
    get,
    web::{Data, Json, Path, Payload},
    HttpRequest, HttpResponse,
};
use actix_web_actors::ws;
use futures_util::future::join_all;
use log::error;
use sdl_parser::{
    node::{NodeType, VM},
    parse_sdl,
};
use std::collections::HashMap;

#[get("")]
pub async fn get_participant_deployments(
    app_state: Data<AppState>,
    user_info: UserInfo,
    keycloak_info: KeycloakInfo,
    exercise: ExerciseInfo,
) -> Result<Json<Vec<ParticipantDeployment>>, RangerError> {
    let deployments = app_state
        .database_address
        .send(GetDeployments(exercise.id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get deployments"))?;

    let deployment_with_members = join_all(deployments.into_iter().map(|deployment| async {
        let is_connected = deployment
            .is_connected(
                user_info.id.clone(),
                &app_state.database_address,
                KeycloakInfo(keycloak_info.clone()),
                app_state.configuration.keycloak.realm.clone(),
            )
            .await
            .unwrap_or(false);

        (deployment, is_connected)
    }))
    .await
    .into_iter()
    .filter_map(|(exercise, is_connected)| {
        if is_connected {
            return Some(exercise);
        }
        None
    })
    .collect::<Vec<_>>();

    let participant_deployments = deployment_with_members
        .into_iter()
        .map(ParticipantDeployment::from)
        .collect();

    Ok(Json(participant_deployments))
}

#[get("")]
pub async fn get_participant_deployment(
    deployment: DeploymentInfo,
) -> Result<Json<ParticipantDeployment>, RangerError> {
    let deployment = deployment.into_inner().into();

    Ok(Json(deployment))
}

#[get("")]
pub async fn get_participant_node_deployment_elements(
    path_variables: Path<(Uuid, Uuid, String)>,
    app_state: Data<AppState>,
    deployment: DeploymentInfo,
) -> Result<Json<Vec<DeploymentElement>>, RangerError> {
    let (_exercise_id, _deployment_id, entity_selector) = path_variables.into_inner();
    let deployment = deployment.into_inner();

    let elements = app_state
        .database_address
        .send(GetDeploymentElementByDeploymentId(deployment.id, false))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get deployment elements"))?;

    let scenario = parse_sdl(&deployment.sdl_schema).map_err(|error| {
        error!("Failed to parse sdl: {error}");
        RangerError::ScenarioParsingFailed
    })?;

    let vm_nodes: HashMap<String, VM> = scenario
        .nodes
        .into_iter()
        .flat_map(|nodes| nodes.into_iter())
        .filter_map(|(node_key, node)| {
            if let NodeType::VM(vm_node) = node.type_field {
                Some((node_key, vm_node))
            } else {
                None
            }
        })
        .collect();

    let node_keys_filtered_by_entity: Vec<String> =
        vm_nodes
            .into_iter()
            .fold(Vec::new(), |mut accumulator, (vm_key, vm_node)| {
                if let Some(roles) = vm_node.roles {
                    roles.iter().for_each(|(_role_key, role)| {
                        if let Some(entities) = &role.entities {
                            if entities.contains(&entity_selector) {
                                accumulator.push(vm_key.clone());
                            }
                        }
                    })
                };
                accumulator
            });

    let entity_node_elements = elements
        .into_iter()
        .filter(|element| node_keys_filtered_by_entity.contains(&element.scenario_reference))
        .collect::<Vec<_>>();

    Ok(Json(entity_node_elements))
}

#[get("")]
pub async fn subscribe_participant_to_deployment(
    req: HttpRequest,
    exercise: ExerciseInfo,
    app_state: Data<AppState>,
    stream: Payload,
) -> Result<HttpResponse, RangerError> {
    log::debug!(
        "Subscribing participant websocket to deployment {}",
        exercise.id
    );
    let manager_address = app_state.websocket_manager_address.clone();
    let exercise_socket = ExerciseWebsocket::new(exercise.id, manager_address);
    log::debug!(
        "Created participant websocket for deployment {}",
        exercise.id
    );
    ws::start(exercise_socket, &req, stream).map_err(|error| {
        error!("Websocket connection error: {error}");
        RangerError::WebsocketFailed
    })
}
