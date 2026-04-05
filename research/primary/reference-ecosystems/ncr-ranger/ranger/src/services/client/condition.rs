use crate::{
    constants::{BIG_DECIMAL_ONE, BIG_DECIMAL_ZERO},
    models::{DeploymentElement, ElementStatus, NewConditionMessage},
    services::{
        database::{
            condition::CreateConditionMessage, deployment::GetDeployment, event::GetEvent, Database,
        },
        deployer::DeployerDistribution,
    },
    utilities::try_some,
};

use super::{DeploymentClient, DeploymentClientResponse, DeploymentInfo};
use crate::models::helpers::uuid::Uuid;
use actix::{
    Actor, Addr, Context, Handler, Message, ResponseActFuture, ResponseFuture, WrapFuture,
};
use anyhow::{anyhow, Ok, Result};
use async_trait::async_trait;
use bigdecimal::{BigDecimal, FromPrimitive};
use log::{debug, warn};
use ranger_grpc::{
    condition_service_client::ConditionServiceClient, Condition as GrpcCondition,
    ConditionStreamResponse, Identifier,
};
use sdl_parser::metric::Metric;
use std::any::Any;
use tonic::{transport::Channel, Streaming};

impl DeploymentInfo for GrpcCondition {
    fn get_deployment(&self) -> GrpcCondition {
        self.clone()
    }
    fn as_any(&self) -> &dyn Any {
        self
    }
}
pub struct ConditionClient {
    condition_client: ConditionServiceClient<Channel>,
}

impl ConditionClient {
    pub async fn new(server_address: String) -> Result<Self> {
        Ok(Self {
            condition_client: ConditionServiceClient::connect(server_address).await?,
        })
    }
}

impl Actor for ConditionClient {
    type Context = Context<Self>;
}

#[async_trait]
impl DeploymentClient<Box<dyn DeploymentInfo>> for Addr<ConditionClient> {
    async fn deploy(
        &mut self,
        deployment_struct: Box<dyn DeploymentInfo>,
    ) -> Result<DeploymentClientResponse> {
        let deployment = CreateCondition(
            deployment_struct
                .as_any()
                .downcast_ref::<GrpcCondition>()
                .unwrap()
                .clone(),
        );
        let identifier = self.send(deployment).await??;

        let stream = self
            .send(CreateConditionStream(Identifier {
                value: identifier.value.to_owned(),
            }))
            .await??;
        Ok(DeploymentClientResponse::ConditionResponse((
            identifier, stream,
        )))
    }

    async fn undeploy(&mut self, handler_reference: String) -> Result<()> {
        let undeploy = DeleteCondition(Identifier {
            value: handler_reference,
        });
        self.send(undeploy).await??;

        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<Identifier>")]
pub struct CreateCondition(pub GrpcCondition);

impl Handler<CreateCondition> for ConditionClient {
    type Result = ResponseFuture<Result<Identifier>>;

    fn handle(&mut self, msg: CreateCondition, _ctx: &mut Self::Context) -> Self::Result {
        let condition_deployment = msg.0;
        let mut client = self.condition_client.clone();

        Box::pin(async move {
            let result = client
                .create(tonic::Request::new(condition_deployment))
                .await?;
            Ok(result.into_inner())
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<Streaming<ConditionStreamResponse>>")]
pub struct CreateConditionStream(pub Identifier);

impl Handler<CreateConditionStream> for ConditionClient {
    type Result = ResponseFuture<Result<Streaming<ConditionStreamResponse>>>;

    fn handle(&mut self, msg: CreateConditionStream, _ctx: &mut Self::Context) -> Self::Result {
        let identifier = msg.0;
        let mut client = self.condition_client.clone();

        Box::pin(async move {
            let stream = client
                .stream(tonic::Request::new(identifier))
                .await?
                .into_inner();

            Ok(stream)
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct DeleteCondition(pub Identifier);

impl Handler<DeleteCondition> for ConditionClient {
    type Result = ResponseFuture<Result<()>>;

    fn handle(&mut self, msg: DeleteCondition, _ctx: &mut Self::Context) -> Self::Result {
        let identifier = msg.0;
        let mut client = self.condition_client.clone();
        Box::pin(async move {
            let result = client.delete(tonic::Request::new(identifier)).await;
            if let Err(status) = result {
                return Err(anyhow::anyhow!("{:?}", status));
            }
            Ok(())
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct ConditionStream {
    pub exercise_id: Uuid,
    pub condition_deployment_element: DeploymentElement,
    pub node_deployment_element: DeploymentElement,
    pub database_address: Addr<Database>,
    pub condition_stream: Streaming<ConditionStreamResponse>,
    pub condition_metric: Option<(String, Metric)>,
}

impl Handler<ConditionStream> for DeployerDistribution {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, mut msg: ConditionStream, _ctx: &mut Self::Context) -> Self::Result {
        Box::pin(
            async move {
                let virtual_machine_id = try_some(
                    msg.node_deployment_element.handler_reference,
                    "Deployment element handler reference not found",
                )?;

                debug!(
                    "Finished deploying '{condition_name}' on '{node_name}', starting stream",
                    condition_name = msg.condition_deployment_element.scenario_reference,
                    node_name = msg.node_deployment_element.scenario_reference,
                );

                let condition_id: Uuid = msg.condition_deployment_element
                    .clone()
                    .handler_reference
                    .ok_or_else(|| anyhow!("Condition id not found"))?
                    .as_str()
                    .try_into()?;

                while let Some(stream_item) = msg.condition_stream.message().await? {
                    msg.condition_deployment_element.error_message = None;

                    let value = BigDecimal::from_f32(stream_item.command_return_value)
                        .ok_or_else(|| anyhow!("Error converting Condition Return value"))?;

                    debug!(
                        "Received Condition Id: {:?}, Value: {:?}",
                        stream_item.response,
                        stream_item.command_return_value,
                    );

                    if let Some(event_id) = msg.condition_deployment_element.event_id {
                        let event = msg.database_address.send(GetEvent(event_id)).await??;
                        let condition_status = msg.condition_deployment_element.status;
                        let condition_is_met = value == *BIG_DECIMAL_ONE;
                        if event.end < chrono::Utc::now().naive_utc() {
                            debug!(
                                "Event '{}' window has ended, closing '{condition_name}' stream for '{node_name}'",
                                event.name,
                                condition_name =
                                msg.condition_deployment_element.scenario_reference,
                                node_name = msg.node_deployment_element.scenario_reference
                            );
                            break;
                        }
                        if condition_status == ElementStatus::ConditionSuccess && event.has_triggered {
                            debug!(
                                "Event '{}' has triggered, closing '{condition_name}' stream for '{node_name}'",
                                event.name,
                                condition_name =
                                msg.condition_deployment_element.scenario_reference,
                                node_name = msg.node_deployment_element.scenario_reference
                            );
                            break;
                        }
                        if condition_is_met {
                            if condition_status == ElementStatus::ConditionPolling {
                                msg.condition_deployment_element.status = ElementStatus::ConditionSuccess;
                            }
                        } else if condition_status == ElementStatus::ConditionSuccess || condition_status == ElementStatus::ConditionWarning {
                            msg.condition_deployment_element.status = ElementStatus::ConditionPolling;
                        }
                        msg.condition_deployment_element.update(
                            &msg.database_address,
                            msg.exercise_id,
                            msg.condition_deployment_element.status,
                            msg.condition_deployment_element.handler_reference.clone(),
                        ).await?;
                    }

                    let deployment = msg.database_address.send(GetDeployment(msg.node_deployment_element.deployment_id)).await??;
                    if deployment.end < chrono::Utc::now().naive_utc() {
                        debug!(
                            "Deployment '{}' has ended, closing '{condition_name}' stream for '{node_name}'",
                            deployment.name,
                            condition_name =
                            msg.condition_deployment_element.scenario_reference,
                            node_name = msg.node_deployment_element.scenario_reference
                        );

                        msg.condition_deployment_element.update(
                            &msg.database_address,
                            msg.exercise_id,
                            ElementStatus::ConditionClosed,
                            msg.condition_deployment_element.handler_reference.clone(),
                        ).await?;

                        break;
                    }

                    if value > *BIG_DECIMAL_ONE {
                        let warning_message = format!(
                            "Ignoring Condition '{condition_name}' from VM '{vm_name}', value that is greater than 1.0: '{value}'",
                            condition_name = msg.condition_deployment_element.scenario_reference,
                            vm_name = msg.node_deployment_element.scenario_reference,
                        );
                        warn!("{}", warning_message);

                        msg.condition_deployment_element.error_message = Some(warning_message);
                        msg.condition_deployment_element.update(
                            &msg.database_address,
                            msg.exercise_id,
                            ElementStatus::ConditionWarning,
                            msg.condition_deployment_element.handler_reference.clone(),
                        ).await?;

                        continue;
                    } else if value < *BIG_DECIMAL_ZERO {
                        let warning_message = format!(
                            "Ignoring Condition '{condition_name}' from VM '{vm_name}', value that is less than 0.0: '{value}'",
                            condition_name = msg.condition_deployment_element.scenario_reference,
                            vm_name = msg.node_deployment_element.scenario_reference,
                        );
                        warn!("{}", warning_message);

                        msg.condition_deployment_element.error_message = Some(warning_message);
                        msg.condition_deployment_element.update(
                            &msg.database_address,
                            msg.exercise_id,
                            ElementStatus::ConditionWarning,
                            msg.condition_deployment_element.handler_reference.clone(),
                        ).await?;

                        continue;
                    }

                    msg.database_address
                        .send(CreateConditionMessage(
                            NewConditionMessage::new(
                                msg.exercise_id,
                                msg.condition_deployment_element.deployment_id,
                                Uuid::try_from(virtual_machine_id.as_str())?,
                                msg.condition_deployment_element.scenario_reference.to_owned(),
                                condition_id,
                                value,
                            ),
                            msg.condition_metric.clone(),
                            msg.node_deployment_element.scenario_reference.clone(),
                        ))
                        .await??;
                }
                Ok(())
            }
            .into_actor(self),
        )
    }
}
