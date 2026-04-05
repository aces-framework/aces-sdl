use actix::{Actor, Handler, Message};
use anyhow::{anyhow, Ok, Result};
use sdl_parser::{
    feature::Feature,
    infrastructure::InfraNode,
    node::{Node, NodeType, Role},
    Scenario,
};
use std::collections::HashMap;

#[derive(Default)]
pub struct Scheduler;

impl Actor for Scheduler {
    type Context = actix::Context<Self>;
}

impl Scheduler {
    pub fn new() -> Self {
        Scheduler
    }
}

#[derive(Message, Debug, PartialEq)]
#[rtype(result = "Result<Vec<Vec<(String, Node, InfraNode)>>>")]
pub struct CreateDeploymentSchedule(pub(crate) Scenario);

impl CreateDeploymentSchedule {
    fn create_node_name(infra_node: &InfraNode, node_name: String, count: u32) -> String {
        match infra_node.count {
            0 | 1 => node_name,
            _ => format!("{node_name}-{count}"),
        }
    }

    pub fn generate(&self) -> Result<Vec<Vec<(String, Node, InfraNode)>>> {
        let scenario = &self.0;
        let dependencies = scenario.get_node_dependencies()?;
        let tranches = dependencies.generate_tranches()?;

        if let Some(infrastructure) = &scenario.infrastructure {
            if let Some(nodes) = &scenario.nodes {
                let mut node_deployments: Vec<Vec<(String, Node, InfraNode)>> = Vec::new();
                tranches.iter().try_for_each(|tranche| {
                    let mut new_tranche = Vec::new();
                    tranche.iter().try_for_each(|node_name| {
                        if let Some(infra_value) = infrastructure.get(node_name) {
                            let node_value =
                                nodes.get(node_name).ok_or_else(|| anyhow!("Node value"))?;
                            for n in 0..infra_value.count {
                                new_tranche.push((
                                    Self::create_node_name(
                                        infra_value,
                                        node_name.clone(),
                                        n as u32,
                                    ),
                                    node_value.clone(),
                                    infra_value.clone(),
                                ));
                            }
                        }
                        Ok(())
                    })?;
                    node_deployments.push(new_tranche);
                    Ok(())
                })?;
                return Ok(node_deployments);
            }
        }

        Ok(vec![vec![]])
    }
}

#[derive(Message, Debug, PartialEq)]
#[rtype(result = "Result<Vec<Vec<(String, Feature, Role)>>>")]
pub struct CreateFeatureDeploymentSchedule(pub(crate) Scenario, pub(crate) Node);

impl CreateFeatureDeploymentSchedule {
    pub fn generate(&self) -> Result<Vec<Vec<(String, Feature, Role)>>> {
        let scenario = &self.0;
        let node = &self.1;
        let mut tranches_with_roles: HashMap<&String, Vec<Vec<String>>> = HashMap::new();
        let vm_node = match &node.type_field {
            NodeType::VM(vm_node) => vm_node,
            _ => return Ok(vec![vec![]]),
        };

        for (node_feature_name, node_feature_role) in vm_node.features.iter() {
            let dependencies = scenario.get_a_node_features_dependencies(node_feature_name)?;
            let mut tranches = dependencies.generate_tranches()?;

            if let Some(existing_tranches) = tranches_with_roles.get(node_feature_role) {
                tranches.extend(existing_tranches.to_owned())
            }

            tranches_with_roles.insert(node_feature_role, tranches);
        }
        let roles = vm_node.roles.clone().unwrap_or_default();

        if let Some(features) = &scenario.features {
            let mut feature_schedule: Vec<Vec<(String, Feature, Role)>> = Vec::new();

            tranches_with_roles
                .iter()
                .try_for_each(|(role, tranches)| {
                    tranches.iter().try_for_each(|tranche| {
                        let mut schedule_entry = Vec::new();

                        tranche.iter().try_for_each(|feature_name| {
                            let feature_value = features
                                .get(feature_name)
                                .ok_or_else(|| anyhow!("Feature in Scenario not found"))?;

                            let username = roles
                                .get(role.to_owned())
                                .ok_or_else(|| anyhow!("Username in Roles list not found"))?;

                            schedule_entry.push((
                                feature_name.clone(),
                                feature_value.clone(),
                                username.to_owned(),
                            ));
                            Ok(())
                        })?;
                        feature_schedule.push(schedule_entry);
                        Ok(())
                    })?;
                    Ok(())
                })?;
            return Ok(feature_schedule);
        }

        Ok(vec![vec![]])
    }
}

impl Handler<CreateDeploymentSchedule> for Scheduler {
    type Result = Result<Vec<Vec<(String, Node, InfraNode)>>>;

    fn handle(&mut self, message: CreateDeploymentSchedule, _: &mut Self::Context) -> Self::Result {
        message.generate()
    }
}

impl Handler<CreateFeatureDeploymentSchedule> for Scheduler {
    type Result = Result<Vec<Vec<(String, Feature, Role)>>>;

    fn handle(
        &mut self,
        message: CreateFeatureDeploymentSchedule,
        _: &mut Self::Context,
    ) -> Self::Result {
        message.generate()
    }
}
