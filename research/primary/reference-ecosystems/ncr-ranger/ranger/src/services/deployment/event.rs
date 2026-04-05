use super::inject::{DeployableInject, InjectProperties};
use super::node::NodeDeploymentInfo;
use super::Database;
use crate::constants::{EVENT_POLLER_RETRY_DURATION, NAIVEDATETIME_DEFAULT_VALUE};
use crate::models::{helpers::uuid::Uuid, Deployment, ElementStatus, Exercise};
use crate::services::database::{
    deployment::GetDeploymentElementByEventId,
    event::{CreateEvent, UpdateEvent},
};
use crate::services::deployment::inject::InjectDeployment;
use crate::utilities::{event::await_event_start, try_some};
use crate::Addressor;
use actix::{Actor, Addr, Context, Handler, Message, ResponseActFuture, WrapFuture};
use anyhow::{Ok, Result};
use async_trait::async_trait;
use chrono::Utc;
use futures_util::future::join_all;
use log::debug;
use sdl_parser::{
    event::Event,
    inject::Inject,
    node::{NodeType, VM},
    Scenario,
};
use std::collections::HashMap;
use tokio::time::sleep;

#[derive(Debug, Clone)]
pub struct DeploymentEvent {
    pub id: Uuid,
    pub sdl_key: String,
    pub sdl_event: Event,
    pub name: Option<String>,
    pub injects: Option<Vec<InjectProperties>>,
    pub condition_keys: Option<Vec<String>>,
}

#[async_trait]
pub trait DeployableEvents {
    async fn create_events(
        &self,
        addressor: &Addressor,
        deployment: &Deployment,
    ) -> Result<Vec<DeploymentEvent>>;

    async fn deploy_event_pollers(
        &self,
        addressor: &Addressor,
        exercise: &Exercise,
        deployers: &[String],
        node_deployment_info: &[NodeDeploymentInfo],
        events: Vec<DeploymentEvent>,
    ) -> Result<()>;
}

fn get_event_injects_with_roles(
    event: &Event,
    sdl_injects: &HashMap<String, Inject>,
    node_key: &String,
    vm_node: &VM,
) -> Result<Vec<InjectProperties>> {
    let event_inject_keys = event.injects.clone().unwrap_or_default();
    let event_injects = sdl_injects
        .iter()
        .filter_map(|(inject_key, inject)| {
            if event_inject_keys.contains(inject_key) {
                Some((inject_key.to_owned(), inject.clone()))
            } else {
                None
            }
        })
        .collect::<HashMap<_, _>>();

    let vm_roles = try_some(vm_node.roles.clone(), "VM Node missing Roles")?;

    let event_injects_with_roles = event_injects
        .into_iter()
        .map(|(inject_key, inject)| {
            let role_name = try_some(
                vm_node.injects.get(&inject_key),
                "Inject not found under VM Node Injects",
            )?;
            let role = try_some(vm_roles.get(role_name), "Node Roles missing Role")?;

            Ok(InjectProperties {
                name: inject_key.to_owned(),
                inject: inject.clone(),
                role: role.to_owned(),
                target_node_key: node_key.to_owned(),
            })
        })
        .collect::<Result<Vec<InjectProperties>>>()?;

    Ok(event_injects_with_roles)
}

async fn poll_event(
    addressor: &Addressor,
    deployers: &[String],
    exercise: &Exercise,
    event: &DeploymentEvent,
    node_deployment_infos: &[NodeDeploymentInfo],
) -> Result<()> {
    if event.condition_keys.is_some() || event.injects.is_some() {
        let event_succeeded = addressor
            .event_poller
            .send(StartPolling(
                exercise.id,
                addressor.database.clone(),
                event.clone(),
            ))
            .await??;
        if event_succeeded {
            let event_node_deployment_infos_by_injects = node_deployment_infos
                .iter()
                .filter(|node_deployment_info| {
                    event.injects.as_ref().map_or(false, |injects| {
                        match &node_deployment_info.node_properties.node.type_field {
                            NodeType::VM(vm_node) => injects
                                .iter()
                                .any(|inject| vm_node.injects.contains_key(&inject.name)),
                            _ => false,
                        }
                    })
                })
                .collect::<Vec<_>>();

            let mut deployment_futures = Vec::new();
            for inject_property in event.injects.clone().unwrap_or_default() {
                for node_deployment_info in
                    event_node_deployment_infos_by_injects
                        .iter()
                        .filter(|node_deployment_info| {
                            let vm_node_key = &node_deployment_info
                                .node_properties
                                .deployment_element
                                .scenario_reference;

                            &inject_property.target_node_key == vm_node_key
                        })
                {
                    let inject_deployment = InjectDeployment {
                        addressor: addressor.clone(),
                        deployers: deployers.to_vec(),
                        deployment_element: node_deployment_info
                            .node_properties
                            .deployment_element
                            .clone(),
                        exercise_id: exercise.id,
                        username: inject_property.role.username.clone(),
                        template_id: node_deployment_info.node_properties.template_id,
                        inject_key: inject_property.name.to_owned(),
                        inject: inject_property.inject.clone(),
                    };

                    let deployment_future = inject_deployment.deploy_inject();

                    deployment_futures.push(deployment_future);
                }
            }
            let results = join_all(deployment_futures).await;
            for result in results {
                result?;
            }
        }
    } else {
        addressor
            .event_poller
            .send(StartPollingInformational(
                exercise.id,
                addressor.database.clone(),
                event.id,
            ))
            .await??;
    }

    Ok(())
}

#[async_trait]
impl DeployableEvents for Scenario {
    async fn create_events(
        &self,
        addressor: &Addressor,
        deployment: &Deployment,
    ) -> Result<Vec<DeploymentEvent>> {
        let sdl_events = self.events.clone().unwrap_or_default();
        let sdl_injects = self.injects.clone().unwrap_or_default();

        let referenced_event_keys: Vec<_> =
            self.scripts.as_ref().map_or_else(Vec::new, |scripts| {
                scripts
                    .iter()
                    .flat_map(|(_, script)| script.events.keys())
                    .cloned()
                    .collect()
            });
        let referenced_events = sdl_events
            .into_iter()
            .filter_map(|(event_key, sdl_event)| {
                if referenced_event_keys.contains(&event_key) {
                    Some((event_key, sdl_event))
                } else {
                    None
                }
            })
            .collect::<HashMap<_, _>>();

        let vm_nodes = self.nodes.as_ref().map_or_else(Vec::new, |nodes| {
            nodes
                .iter()
                .filter_map(|(node_key, node)| {
                    if let NodeType::VM(vm_node) = &node.type_field {
                        Some((node_key, vm_node))
                    } else {
                        None
                    }
                })
                .collect()
        });

        let mut deployment_events = Vec::new();
        for (event_key, event) in referenced_events.iter() {
            let event_injects = event.injects.clone().unwrap_or_default();
            let event_inject_vms = vm_nodes
                .iter()
                .filter_map(|(node_key, vm_node)| {
                    if event_injects
                        .iter()
                        .any(|inject_key| vm_node.injects.contains_key(inject_key))
                    {
                        Some((node_key, vm_node))
                    } else {
                        None
                    }
                })
                .collect::<HashMap<_, _>>();

            let event_inject_properties: Option<Vec<_>> = if !event_inject_vms.is_empty() {
                let mut properties = Vec::new();
                for (node_key, vm_node) in event_inject_vms.iter() {
                    let event_injects_with_roles =
                        get_event_injects_with_roles(event, &sdl_injects, node_key, vm_node)?;

                    properties.extend(event_injects_with_roles);
                }
                Some(properties)
            } else {
                None
            };

            let new_event = addressor
                .database
                .send(CreateEvent::new(
                    event_key,
                    event,
                    deployment,
                    self,
                    deployment.id,
                )?)
                .await??;

            let deployment_event = DeploymentEvent {
                id: new_event.id,
                sdl_key: event_key.to_owned(),
                sdl_event: event.clone(),
                name: event.name.clone(),
                injects: event_inject_properties,
                condition_keys: event.conditions.clone(),
            };
            deployment_events.push(deployment_event);
        }

        Ok(deployment_events)
    }

    async fn deploy_event_pollers(
        &self,
        addressor: &Addressor,
        exercise: &Exercise,
        deployers: &[String],
        node_deployment_infos: &[NodeDeploymentInfo],
        events: Vec<DeploymentEvent>,
    ) -> Result<()> {
        let mut futures = Vec::new();
        for event in events.iter() {
            let future = poll_event(addressor, deployers, exercise, event, node_deployment_infos);
            futures.push(future);
        }

        let results = join_all(futures).await;
        results.into_iter().collect::<Result<Vec<()>>>()?;

        Ok(())
    }
}

#[derive(Message, Clone, Debug)]
#[rtype(result = "Result<bool>")]
pub struct StartPolling(Uuid, Addr<Database>, DeploymentEvent);

pub struct EventPoller();

impl Actor for EventPoller {
    type Context = Context<Self>;
}

impl EventPoller {
    pub fn new() -> Self {
        Self()
    }
}

impl Default for EventPoller {
    fn default() -> Self {
        Self::new()
    }
}

impl Handler<StartPolling> for EventPoller {
    type Result = ResponseActFuture<Self, Result<bool>>;

    fn handle(&mut self, msg: StartPolling, _ctx: &mut Context<Self>) -> Self::Result {
        let StartPolling(exercise_id, database_address, event) = msg;

        Box::pin(
            async move {
                let mut updated_event = crate::models::UpdateEvent {
                    has_triggered: false,
                    triggered_at: *NAIVEDATETIME_DEFAULT_VALUE,
                };
                let has_succeeded: bool;
                let is_conditional_event = event.condition_keys.is_some();
                let event =
                    await_event_start(&database_address, event.id, is_conditional_event).await?;

                if is_conditional_event {
                    debug!("Starting Polling for Event '{}'", event.name);
                    loop {
                        let current_time = Utc::now().naive_utc();
                        let condition_deployment_elements = database_address
                            .send(GetDeploymentElementByEventId(event.id, true))
                            .await??;

                        let successful_condition_count = condition_deployment_elements
                            .iter()
                            .filter(|condition| {
                                matches!(condition.status, ElementStatus::ConditionSuccess)
                            })
                            .count();

                        if condition_deployment_elements
                            .len()
                            .eq(&successful_condition_count)
                        {
                            debug!("Event '{}' has been triggered successfully", event.name,);
                            updated_event.has_triggered = true;
                            updated_event.triggered_at = Utc::now().naive_utc();
                            has_succeeded = true;
                            break;
                        } else if current_time > event.end {
                            debug!("Event '{}' deployment window has ended", event.name);
                            has_succeeded = false;
                            break;
                        }

                        sleep(EVENT_POLLER_RETRY_DURATION).await;
                    }
                } else {
                    debug!("Purely timed Event '{}' has been triggered", event.name);
                    updated_event.has_triggered = true;
                    updated_event.triggered_at = Utc::now().naive_utc();
                    has_succeeded = true;
                }

                database_address
                    .send(UpdateEvent(exercise_id, event.id, updated_event))
                    .await??;

                Ok(has_succeeded)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message, Clone, Debug)]
#[rtype(result = "Result<bool>")]
pub struct StartPollingInformational(Uuid, Addr<Database>, Uuid);

impl Handler<StartPollingInformational> for EventPoller {
    type Result = ResponseActFuture<Self, Result<bool>>;

    fn handle(&mut self, msg: StartPollingInformational, _ctx: &mut Context<Self>) -> Self::Result {
        let StartPollingInformational(exercise_id, database_address, event_id) = msg;

        Box::pin(
            async move {
                let mut updated_event = crate::models::UpdateEvent {
                    has_triggered: false,
                    triggered_at: *NAIVEDATETIME_DEFAULT_VALUE,
                };

                await_event_start(&database_address, event_id, false).await?;

                updated_event.has_triggered = true;
                updated_event.triggered_at = Utc::now().naive_utc();

                database_address
                    .send(UpdateEvent(exercise_id, event_id, updated_event))
                    .await??;

                Ok(true)
            }
            .into_actor(self),
        )
    }
}
