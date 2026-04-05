use crate::{
    models::{
        helpers::uuid::Uuid, Deployment, DeploymentElement, ElementStatus, Exercise, NewAccount,
    },
    services::{
        client::{Deployable, DeploymentInfo},
        database::{
            account::CreateAccount,
            deployment::{CreateOrIgnoreDeploymentElement, UpdateDeploymentElement},
            Database,
        },
        deployer::Deploy,
    },
    utilities::try_some,
    Addressor,
};
use actix::Addr;
use anyhow::{anyhow, Ok, Result};
use async_trait::async_trait;
use futures::future::try_join_all;
use log::debug;
use ranger_grpc::{
    capabilities::DeployerType as GrpcDeployerType, Account, Source as GrpcSource, TemplateResponse,
};
use sdl_parser::{
    common::Source as SDLSource,
    node::{NodeType, VM},
    Scenario,
};
use std::collections::HashMap;

impl Deployable for SDLSource {
    fn try_to_deployment_command(&self) -> Result<Box<dyn DeploymentInfo>> {
        Ok(Box::new(GrpcSource {
            name: self.name.clone(),
            version: self.version.clone(),
        }))
    }
}

#[async_trait]
pub trait DeployableTemplates {
    async fn deploy_templates(
        &self,
        addressor: &Addressor,
        deployers: &[String],
        deployment: &Deployment,
        exercise: &Exercise,
    ) -> Result<()>;
}

async fn save_accounts(
    accounts: Vec<Account>,
    database_address: &Addr<Database>,
    template_id: Uuid,
    exercise_id: Uuid,
) -> Result<()> {
    for account in accounts.iter() {
        let password = (!account.password.is_empty()).then_some(account.password.clone());
        let private_key = (!account.private_key.is_empty()).then_some(account.private_key.clone());

        database_address
            .send(CreateAccount(NewAccount {
                id: Uuid::random(),
                template_id,
                username: account.username.to_owned(),
                password,
                private_key,
                exercise_id,
            }))
            .await??;
    }
    Ok(())
}

#[async_trait]
impl DeployableTemplates for Scenario {
    async fn deploy_templates(
        &self,
        addressor: &Addressor,
        deployers: &[String],
        deployment: &Deployment,
        exercise: &Exercise,
    ) -> Result<()> {
        let nodes = match self.nodes.as_ref() {
            Some(nodes) => nodes,
            None => return Ok(()),
        };

        let vm_nodes: HashMap<String, VM> = nodes
            .iter()
            .filter_map(|(name, node)| match &node.type_field {
                NodeType::VM(vm_node) => Some((name.to_owned(), vm_node.to_owned())),
                _ => None,
            })
            .collect();

        try_join_all(vm_nodes.iter().map(|(name, vm_node)| async move {
            let placeholder_template_id = "00000000-0000-0000-0000-000000000000".to_string();
            let source = try_some(vm_node.source.as_ref(), "Template missing source")?;

            let mut deployment_element = addressor
                .database
                .send(CreateOrIgnoreDeploymentElement(
                    exercise.id,
                    DeploymentElement::new(
                        deployment.id,
                        Box::new(source.to_owned()),
                        Some(placeholder_template_id),
                        GrpcDeployerType::Template,
                        ElementStatus::Ongoing,
                    ),
                    true,
                ))
                .await??;

            match addressor
                .distributor
                .send(Deploy(
                    GrpcDeployerType::Template,
                    source.try_to_deployment_command()?,
                    deployers.to_owned(),
                ))
                .await?
            {
                anyhow::Result::Ok(client_response) => {
                    let template_response = TemplateResponse::try_from(client_response)?;
                    let template_id = template_response
                        .identifier
                        .ok_or_else(|| anyhow!("Templater did not return id"))?
                        .value;

                    if !template_response.accounts.is_empty() {
                        save_accounts(
                            template_response.accounts,
                            &addressor.database,
                            Uuid::try_from(template_id.as_str())?,
                            exercise.id,
                        )
                        .await?;
                    }

                    debug!("Node {} deployed with template id {}", name, template_id);

                    deployment_element.status = ElementStatus::Success;
                    deployment_element.handler_reference = Some(template_id);

                    addressor
                        .database
                        .send(UpdateDeploymentElement(
                            exercise.id,
                            deployment_element,
                            true,
                        ))
                        .await??;
                    Ok::<()>(())
                }

                Err(error) => {
                    deployment_element.status = ElementStatus::Failed;
                    deployment_element.error_message = Some(format!(
                        "Handler returned an error while creating a template: {}",
                        error
                    ));
                    addressor
                        .database
                        .send(UpdateDeploymentElement(
                            exercise.id,
                            deployment_element,
                            true,
                        ))
                        .await??;
                    Err(error)
                }
            }
        }))
        .await?;
        Ok(())
    }
}
