use crate::{
    errors::RangerError,
    middleware::{authentication::UserInfo, deployment::DeploymentInfo, exercise::ExerciseInfo},
    models::{
        helpers::uuid::Uuid,
        user::{User, UserAccount},
        Banner, Deployment, DeploymentElement, Exercise, NewBanner, NewBannerWithId, NewDeployment,
        NewDeploymentResource, NewExercise, NewParticipant, NewParticipantResource, Participant,
        Score, UpdateBanner, UpdateExercise,
    },
    roles::RangerRole,
    services::{
        database::{
            account::GetAccount,
            banner::{CreateBanner, DeleteBanner, GetBanner},
            condition::GetConditionMessagesByDeploymentId,
            deployment::{
                CreateDeployment, DeleteDeployment, GetDeploymentElementByDeploymentId,
                GetDeploymentElementByDeploymentIdByScenarioReference, GetDeployments,
            },
            exercise::{CreateExercise, DeleteExercise, GetExercises},
            metric::GetMetrics,
            participant::{CreateParticipant, DeleteParticipant, GetParticipants},
        },
        deployment::{RemoveDeployment, StartDeployment},
        websocket::ExerciseWebsocket,
    },
    utilities::{
        create_database_error_handler, create_mailbox_error_handler,
        scenario::filter_node_roles_by_entity, try_some, Validation,
    },
    AppState,
};
use actix_web::{
    delete, get, post, put,
    web::{Data, Json, Path, Payload},
    HttpRequest, HttpResponse,
};
use actix_web_actors::ws;
use anyhow::Result;
use bigdecimal::BigDecimal;
use futures::future::try_join_all;
use log::{error, info};
use ranger_grpc::capabilities::DeployerType as GrpcDeployerType;
use sdl_parser::{
    entity::Flatten,
    node::{NodeType, VM},
    parse_sdl, Scenario,
};
use std::collections::HashMap;

#[post("")]
pub async fn add_exercise(
    app_state: Data<AppState>,
    exercise: Json<NewExercise>,
) -> Result<Json<Exercise>, RangerError> {
    let exercise = exercise.into_inner();
    exercise.validate()?;

    let exercise = app_state
        .database_address
        .send(CreateExercise(exercise))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Create exercise"))?;
    log::debug!("Created exercise: {}", exercise.id);

    Ok(Json(exercise))
}

#[get("")]
pub async fn get_exercises(app_state: Data<AppState>) -> Result<Json<Vec<Exercise>>, RangerError> {
    let exercises = app_state
        .database_address
        .send(GetExercises)
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get exercises"))?;

    Ok(Json(exercises))
}

#[put("")]
pub async fn update_exercise(
    update_exercise: Json<UpdateExercise>,
    app_state: Data<AppState>,
    exercise: ExerciseInfo,
) -> Result<Json<Exercise>, RangerError> {
    let update_exercise = update_exercise.into_inner();

    let exercise = app_state
        .database_address
        .send(crate::services::database::exercise::UpdateExercise(
            exercise.id,
            update_exercise.clone(),
        ))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Update exercise"))?;
    log::debug!("Updated exercise: {}", exercise.id);

    Ok(Json(exercise))
}

#[get("")]
pub async fn get_exercise(exercise: ExerciseInfo) -> Result<Json<Exercise>, RangerError> {
    let exercise = exercise.into_inner();

    Ok(Json(exercise))
}

#[delete("")]
pub async fn delete_exercise(
    exercise: ExerciseInfo,
    app_state: Data<AppState>,
) -> Result<String, RangerError> {
    app_state
        .database_address
        .send(DeleteExercise(exercise.id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Delete exercise"))?;
    log::debug!("Deleted exercise {}", exercise.id);

    Ok(exercise.id.to_string())
}

#[get("")]
pub async fn get_exercise_deployments(
    exercise: ExerciseInfo,
    app_state: Data<AppState>,
) -> Result<Json<Vec<Deployment>>, RangerError> {
    let deployments = app_state
        .database_address
        .send(GetDeployments(exercise.id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get deployments"))?;

    Ok(Json(deployments))
}

#[post("")]
pub async fn add_exercise_deployment(
    app_state: Data<AppState>,
    deployment_resource: Json<NewDeploymentResource>,
    exercise: ExerciseInfo,
) -> Result<Json<Deployment>, RangerError> {
    let deployment_resource = deployment_resource.into_inner();

    let scenario = Scenario::from_yaml(&deployment_resource.sdl_schema).map_err(|error| {
        error!("Deployment error: {error}");
        RangerError::DeploymentFailed
    })?;
    let deployment = NewDeployment::new(deployment_resource, exercise.id);

    log::debug!(
        "Adding deployment {} for exercise {}",
        exercise.name,
        deployment.name
    );
    let deployment = app_state
        .database_address
        .send(CreateDeployment(deployment))
        .await
        .map_err(create_mailbox_error_handler("Deployment"))?
        .map_err(create_database_error_handler("Create deployment"))?;

    app_state
        .deployment_manager_address
        .do_send(StartDeployment(
            scenario,
            deployment.clone(),
            exercise.into_inner(),
        ));

    Ok(Json(deployment))
}

#[get("")]
pub async fn get_exercise_deployment(
    deployment: DeploymentInfo,
) -> Result<Json<Deployment>, RangerError> {
    let deployment = deployment.into_inner();

    Ok(Json(deployment))
}

#[delete("")]
pub async fn delete_exercise_deployment(
    app_state: Data<AppState>,
    deployment: DeploymentInfo,
    exercise: ExerciseInfo,
) -> Result<String, RangerError> {
    let deployment = deployment.into_inner();
    let deployment_id = deployment.id;
    app_state
        .deployment_manager_address
        .send(RemoveDeployment(exercise.id, deployment))
        .await
        .map_err(create_mailbox_error_handler("Deployment manager"))?
        .map_err(|error| {
            error!("Undeploying error: {error}");
            RangerError::UndeploymentFailed
        })?;

    info!("Deleting deployment {:?}", deployment_id);
    app_state
        .database_address
        .send(DeleteDeployment(deployment_id, false))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Delete deployment"))?;

    Ok(deployment_id.to_string())
}

#[get("deployment_element")]
pub async fn get_exercise_deployment_elements(
    app_state: Data<AppState>,
    deployment: DeploymentInfo,
) -> Result<Json<Vec<DeploymentElement>>, RangerError> {
    let deployment = deployment.into_inner();
    let elements = app_state
        .database_address
        .send(GetDeploymentElementByDeploymentId(deployment.id, false))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get deployment elements"))?;

    Ok(Json(elements))
}

#[get("websocket")]
pub async fn subscribe_to_exercise(
    req: HttpRequest,
    exercise: ExerciseInfo,
    app_state: Data<AppState>,
    stream: Payload,
) -> Result<HttpResponse, RangerError> {
    log::debug!("Subscribing websocket to exercise {}", exercise.id);
    let manager_address = app_state.websocket_manager_address.clone();
    let exercise_socket = ExerciseWebsocket::new(exercise.id, manager_address);
    log::debug!("Created websocket for exercise {}", exercise.id);
    ws::start(exercise_socket, &req, stream).map_err(|error| {
        error!("Websocket connection error: {error}");
        RangerError::WebsocketFailed
    })
}

#[post("participant")]
pub async fn add_participant(
    app_state: Data<AppState>,
    participant_resource: Json<NewParticipantResource>,
    deployment: DeploymentInfo,
) -> Result<Json<Participant>, RangerError> {
    let participant_resource = participant_resource.into_inner();

    let scenario = parse_sdl(&deployment.sdl_schema).map_err(|error| {
        error!("Failed to parse sdl: {error}");
        RangerError::ScenarioParsingFailed
    })?;

    if let Some(entities) = scenario.entities {
        match entities.flatten().get(&participant_resource.selector) {
            Some(_) => {
                let participant = app_state
                    .database_address
                    .send(CreateParticipant(NewParticipant {
                        id: Uuid::random(),
                        deployment_id: deployment.id,
                        selector: participant_resource.selector,
                        user_id: participant_resource.user_id,
                    }))
                    .await
                    .map_err(create_mailbox_error_handler("Database"))?
                    .map_err(create_database_error_handler("Create participant"))?;

                Ok(Json(participant))
            }
            None => Err(RangerError::EntityNotFound),
        }
    } else {
        Err(RangerError::EntityNotFound)
    }
}

#[get("participant")]
pub async fn get_admin_participants(
    app_state: Data<AppState>,
    deployment: DeploymentInfo,
) -> Result<Json<Vec<Participant>>, RangerError> {
    let participants = app_state
        .database_address
        .send(GetParticipants(deployment.id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get participants"))?;
    Ok(Json(participants))
}

#[delete("participant/{participant_uuid}")]
pub async fn delete_participant(
    path_variables: Path<(Uuid, Uuid, Uuid)>,
    app_state: Data<AppState>,
) -> Result<String, RangerError> {
    let (_, _, participant_uuid) = path_variables.into_inner();
    app_state
        .database_address
        .send(DeleteParticipant(participant_uuid))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Delete deployments"))?;
    Ok(participant_uuid.to_string())
}

#[get("score")]
pub async fn get_exercise_deployment_scores(
    path_variables: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
    deployment: DeploymentInfo,
) -> Result<Json<Vec<Score>>, RangerError> {
    let (_exercise_uuid, deployment_uuid) = path_variables.into_inner();
    let scenario = parse_sdl(&deployment.sdl_schema).map_err(|error| {
        error!("Failed to parse sdl: {error}");
        RangerError::ScenarioParsingFailed
    })?;

    let mut condition_messages = app_state
        .database_address
        .send(GetConditionMessagesByDeploymentId(deployment_uuid))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get condition_messages"))?;
    condition_messages.retain(|condition| {
        condition.created_at > deployment.start && condition.created_at < deployment.end
    });

    let scenario_metrics = match scenario.metrics {
        Some(metrics) => metrics,
        None => return Ok(Json(vec![])),
    };

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

    let manual_metrics = app_state
        .database_address
        .send(GetMetrics(deployment.id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get Manual Metrics"))?;

    let mut scores: Vec<Score> = manual_metrics.into_iter().map(Into::into).collect();

    for condition_message in condition_messages.iter() {
        if let Some((metric_key, metric)) = scenario_metrics.iter().find(|(_, metric)| {
            metric
                .condition
                .eq(&Some(condition_message.clone().condition_name))
        }) {
            if let Some(vm_name) =
                vm_scenario_refs_by_id.get(&condition_message.virtual_machine_id.to_string())
            {
                scores.push(Score::new(
                    condition_message.exercise_id,
                    condition_message.deployment_id,
                    metric.name.clone(),
                    metric_key.to_owned(),
                    vm_name.to_owned(),
                    condition_message.clone().value * BigDecimal::from(metric.max_score),
                    condition_message.created_at,
                ))
            }
        }
    }

    Ok(Json(scores))
}

#[get("users")]
pub async fn get_exercise_deployment_users(
    app_state: Data<AppState>,
    user_details: UserInfo,
    deployment: DeploymentInfo,
) -> Result<Json<Vec<User>>, RangerError> {
    let scenario = parse_sdl(&deployment.sdl_schema).map_err(|error| {
        error!("Failed to parse sdl: {error}");
        RangerError::ScenarioParsingFailed
    })?;

    if let (Some(scenario_nodes), Some(_infrastructure)) = (scenario.nodes, scenario.infrastructure)
    {
        let vm_nodes = scenario_nodes
            .into_iter()
            .filter_map(|node| {
                if let NodeType::VM(vm_node) = node.1.type_field {
                    Some((node.0, vm_node))
                } else {
                    None
                }
            })
            .collect::<HashMap<String, VM>>();

        let requesters_nodes = match user_details.role {
            RangerRole::Admin => vm_nodes,
            RangerRole::Participant => {
                let participants = app_state
                    .database_address
                    .send(GetParticipants(deployment.id))
                    .await
                    .map_err(create_mailbox_error_handler("Database"))?
                    .map_err(create_database_error_handler("Get participants"))?;
                let participant = participants
                    .into_iter()
                    .filter_map(
                        |participant| match participant.user_id.eq(&user_details.id) {
                            true => Some(participant),
                            false => None,
                        },
                    )
                    .last()
                    .ok_or(RangerError::DatabaseRecordNotFound)?;
                let selector = participant.selector.replace("entities.", "");

                vm_nodes.into_iter().fold(
                    HashMap::new(),
                    |mut node_accumulator, (node_name, mut node)| {
                        if let Some(node_roles) = node.roles {
                            let filtered_node_roles =
                                filter_node_roles_by_entity(node_roles, selector.as_str());

                            if !filtered_node_roles.is_empty() {
                                node.roles = Some(filtered_node_roles);
                                node_accumulator.insert(node_name, node.clone());
                            }
                        }

                        node_accumulator
                    },
                )
            }
            RangerRole::Client => {
                return Err(RangerError::AccessForbidden);
            }
        };

        let roles_by_node = try_join_all(requesters_nodes.into_iter().map(|node| async {
            let source = try_some(node.1.source, "Node has no source")?;
            let sdl_roles = try_some(node.1.roles, "Node has no roles")?;
            let roles = sdl_roles.into_iter().map(|role| role.1).collect::<Vec<_>>();
            let template_deployment_element = app_state
                .database_address
                .send(GetDeploymentElementByDeploymentIdByScenarioReference(
                    deployment.id,
                    Box::new(source.clone()),
                    false,
                ))
                .await??;
            let vm_deployment_element = app_state
                .database_address
                .send(GetDeploymentElementByDeploymentIdByScenarioReference(
                    deployment.id,
                    Box::new(node.0),
                    false,
                ))
                .await??;

            let template_id_result = try_some(
                template_deployment_element.handler_reference,
                "Deployment element missing template id",
            )?;
            let template_id = Uuid::try_from(template_id_result.as_str())?;

            if let Some(vm_id_string) = vm_deployment_element.handler_reference {
                let vm_id = Uuid::try_from(vm_id_string.as_str())?;
                Ok((template_id, Some(vm_id), roles))
            } else {
                Ok((template_id, None, roles))
            }
        }))
        .await
        .map_err(create_database_error_handler(
            "Error getting node credentials",
        ))?;

        let users = try_join_all(
            roles_by_node
                .iter()
                .filter_map(|(template_id, vm_id, roles)| {
                    vm_id.as_ref().map(|vm_id| async {
                        let accounts = try_join_all(roles.iter().map(|role| async {
                            let template_account: UserAccount = app_state
                                .database_address
                                .clone()
                                .send(GetAccount(*template_id, role.username.to_owned()))
                                .await??
                                .into();
                            Ok(template_account)
                        }))
                        .await
                        .map_err(create_database_error_handler(
                            "Error getting account information",
                        ))?;
                        Ok(User {
                            vm_id: *vm_id,
                            accounts,
                        })
                    })
                })
                .collect::<Vec<_>>(),
        )
        .await
        .map_err(create_database_error_handler(
            "Error gathering account information",
        ))?;
        Ok(Json(users))
    } else {
        Ok(Json(vec![]))
    }
}

#[post("")]
pub async fn add_banner(
    path_variable: Path<Uuid>,
    app_state: Data<AppState>,
    new_banner: Json<NewBanner>,
) -> Result<Json<Banner>, RangerError> {
    let exercise_id = path_variable.into_inner();
    let new_banner = new_banner.into_inner();
    let new_banner_with_id = NewBannerWithId {
        exercise_id,
        name: new_banner.name,
        content: new_banner.content,
    };
    let banner = app_state
        .database_address
        .send(CreateBanner(new_banner_with_id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Create banner"))?;
    log::debug!("Created banner: {}", banner.exercise_id);
    Ok(Json(banner))
}

#[get("")]
pub async fn get_banner(
    path_variable: Path<Uuid>,
    app_state: Data<AppState>,
) -> Result<Json<Banner>, RangerError> {
    let exercise_id = path_variable.into_inner();
    let banners = app_state
        .database_address
        .send(GetBanner(exercise_id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get banner"))?;
    Ok(Json(banners))
}

#[put("")]
pub async fn update_banner(
    path_variable: Path<Uuid>,
    update_banner: Json<UpdateBanner>,
    app_state: Data<AppState>,
) -> Result<Json<Banner>, RangerError> {
    let update_banner = update_banner.into_inner();
    let exercise_id = path_variable.into_inner();
    let banner = app_state
        .database_address
        .send(crate::services::database::banner::UpdateBanner(
            exercise_id,
            update_banner,
        ))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Update banner"))?;
    log::debug!("Updated banner: {}", banner.exercise_id);
    Ok(Json(banner))
}

#[delete("")]
pub async fn delete_banner(
    path_variable: Path<Uuid>,
    app_state: Data<AppState>,
) -> Result<String, RangerError> {
    let exercise_id = path_variable.into_inner();
    app_state
        .database_address
        .send(DeleteBanner(exercise_id))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Delete banner"))?;
    log::debug!("Deleted banner {}", exercise_id);
    Ok(exercise_id.to_string())
}
