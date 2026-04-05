use super::node::NodeProperties;
use crate::models::helpers::uuid::Uuid;
use crate::models::{DeploymentElement, ElementStatus, Exercise};
use crate::services::database::account::GetAccount;
use crate::services::database::deployment::{CreateDeploymentElement, UpdateDeploymentElement};
use crate::services::deployer::Deploy;
use crate::services::scheduler::CreateFeatureDeploymentSchedule;
use crate::Addressor;
use anyhow::{anyhow, Ok, Result};
use async_trait::async_trait;
use futures::future::try_join_all;
use log::debug;
use ranger_grpc::capabilities::DeployerType as GrpcDeployerType;
use ranger_grpc::{
    Account as GrpcAccount, ExecutorResponse, Feature as GrpcFeature,
    FeatureType as GrpcFeatureType, Source as GrpcSource,
};
use sdl_parser::{feature::FeatureType, Scenario};

#[async_trait]
pub trait DeployableFeatures {
    async fn deploy_scenario_features(
        &self,
        addressor: &Addressor,
        exercise: &Exercise,
        deployers: &[String],
        deployed_nodes: &[NodeProperties],
    ) -> Result<()>;
}
#[async_trait]
impl DeployableFeatures for Scenario {
    async fn deploy_scenario_features(
        &self,
        addressor: &Addressor,
        exercise: &Exercise,
        deployers: &[String],
        deployed_nodes: &[NodeProperties],
    ) -> Result<()> {
        if self.features.is_some() {
            try_join_all(deployed_nodes.iter().map(|deployed_node| async move {
                (
                    addressor.clone(),
                    deployers.to_owned(),
                    self.clone(),
                    exercise.id,
                    deployed_node,
                )
                    .deploy_node_features()
                    .await?;
                Ok(())
            }))
            .await?;
        }
        Ok(())
    }
}

#[async_trait]
pub trait DeployableNodeFeatures {
    async fn deploy_node_features(&self) -> Result<()>;
}

#[async_trait]
impl DeployableNodeFeatures for (Addressor, Vec<String>, Scenario, Uuid, &NodeProperties) {
    async fn deploy_node_features(&self) -> Result<()> {
        let (addressor, deployers, scenario, exercise_id, deployed_node) = self;
        let NodeProperties {
            node,
            deployment_element,
            template_id,
        } = deployed_node;

        let deployment_schedule = addressor
            .scheduler
            .send(CreateFeatureDeploymentSchedule(
                scenario.clone(),
                node.clone(),
            ))
            .await??;

        for tranche in deployment_schedule.iter() {
            try_join_all(
                tranche
                    .iter()
                    .map(|(feature_name, feature, role)| async move {
                        debug!(
                            "Deploying feature '{feature_name}' for VM {node_name}",
                            node_name = deployment_element.scenario_reference
                        );

                        let virtual_machine_id_string = deployment_element
                            .handler_reference
                            .clone()
                            .ok_or_else(|| {
                                anyhow!("Deployment element handler reference not found")
                            })?;

                        let virtual_machine_id =
                            Uuid::try_from(virtual_machine_id_string.as_str())?;

                        let feature_source = feature
                            .source
                            .clone()
                            .ok_or_else(|| anyhow!("Feature source not found"))?;

                        let mut feature_deployment_element = addressor
                            .database
                            .send(CreateDeploymentElement(
                                *exercise_id,
                                DeploymentElement::new_ongoing(
                                    deployment_element.deployment_id,
                                    Box::new(feature_name.to_string()),
                                    GrpcDeployerType::Feature,
                                    None,
                                    Some(virtual_machine_id),
                                ),
                                true,
                            ))
                            .await??;

                        let feature_type = match feature.feature_type.clone() {
                            FeatureType::Service => GrpcFeatureType::Service,
                            FeatureType::Artifact => GrpcFeatureType::Artifact,
                            FeatureType::Configuration => GrpcFeatureType::Configuration,
                        };

                        let account = addressor
                            .database
                            .send(GetAccount(*template_id, role.username.to_owned()))
                            .await??;

                        let feature_deployment = Box::new(GrpcFeature {
                            name: feature_name.to_owned(),
                            virtual_machine_id: virtual_machine_id_string,
                            feature_type: feature_type.into(),
                            account: Some(GrpcAccount {
                                username: account.username,
                                password: account.password.unwrap_or_default(),
                                private_key: account.private_key.unwrap_or_default(),
                            }),
                            source: Some(GrpcSource {
                                name: feature_source.name,
                                version: feature_source.version,
                            }),
                            environment: feature.environment.clone().unwrap_or_default(),
                        });

                        {
                            match addressor
                                .distributor
                                .send(Deploy(
                                    GrpcDeployerType::Feature,
                                    feature_deployment,
                                    deployers.to_owned(),
                                ))
                                .await?
                            {
                                anyhow::Result::Ok(result) => {
                                    let feature_response = ExecutorResponse::try_from(result)?;

                                    let id = feature_response
                                        .clone()
                                        .identifier
                                        .ok_or_else(|| {
                                            anyhow!("Successful Feature response did not supply Identifier")
                                        })?
                                        .value;

                                    debug!(
                                        "Feature: '{feature_name}' stdout: {:#?}. stderr: {:#?}",
                                        feature_response.stdout, feature_response.stderr
                                    );

                                    feature_deployment_element.status = ElementStatus::Success;
                                    feature_deployment_element.handler_reference = Some(id);
                                    feature_deployment_element
                                    .set_stdout_and_stderr(&feature_response);

                                    addressor
                                        .database
                                        .send(UpdateDeploymentElement(
                                            *exercise_id,
                                            feature_deployment_element,
                                            true,
                                        ))
                                        .await??;
                                    Ok(())
                                }
                                Err(err) => {
                                    feature_deployment_element.status = ElementStatus::Failed;
                                    feature_deployment_element.error_message = Some(format!(
                                        "Handler returned an error while creating a feature: {}",
                                        err
                                    ));
                                    addressor
                                        .database
                                        .send(UpdateDeploymentElement(
                                            *exercise_id,
                                            feature_deployment_element,
                                            true,
                                        ))
                                        .await??;
                                    Err(err)
                                }
                            }
                        }
                    })
                    .collect::<Vec<_>>(),
            )
            .await?;
        }
        Ok(())
    }
}
