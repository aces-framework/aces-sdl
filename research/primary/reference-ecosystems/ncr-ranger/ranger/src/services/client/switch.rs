use super::{DeploymentClient, DeploymentClientResponse, DeploymentInfo};
use actix::{Actor, Addr, Context, Handler, Message, ResponseFuture};
use anyhow::{Ok, Result};
use async_trait::async_trait;
use ranger_grpc::{switch_service_client::SwitchServiceClient, DeploySwitch, Identifier};
use std::any::Any;
use tonic::transport::Channel;

impl DeploymentInfo for DeploySwitch {
    fn get_deployment(&self) -> DeploySwitch {
        self.clone()
    }
    fn as_any(&self) -> &dyn Any {
        self
    }
}

#[async_trait]
impl DeploymentClient<Box<dyn DeploymentInfo>> for Addr<SwitchClient> {
    async fn deploy(
        &mut self,
        deployment_struct: Box<dyn DeploymentInfo>,
    ) -> Result<DeploymentClientResponse> {
        let deployment = CreateSwitch(
            deployment_struct
                .as_any()
                .downcast_ref::<DeploySwitch>()
                .unwrap()
                .clone(),
        );
        let identifier = self.send(deployment).await??;

        Ok(DeploymentClientResponse::Identifier(identifier))
    }

    async fn undeploy(&mut self, handler_reference: String) -> Result<()> {
        let undeploy = DeleteSwitch(Identifier {
            value: handler_reference,
        });
        self.send(undeploy).await??;

        Ok(())
    }
}

pub struct SwitchClient(SwitchServiceClient<Channel>);

impl Actor for SwitchClient {
    type Context = Context<Self>;
}

impl SwitchClient {
    pub async fn new(server_address: String) -> Result<Self> {
        Ok(Self(
            SwitchServiceClient::connect(server_address.clone()).await?,
        ))
    }
}

#[derive(Message)]
#[rtype(result = "Result<Identifier, anyhow::Error>")]
pub struct CreateSwitch(pub DeploySwitch);

impl Handler<CreateSwitch> for SwitchClient {
    type Result = ResponseFuture<Result<Identifier>>;

    fn handle(&mut self, msg: CreateSwitch, _ctx: &mut Self::Context) -> Self::Result {
        let node_deployment = msg.0;
        let mut client = self.0.clone();
        Box::pin(async move {
            let result = client.create(tonic::Request::new(node_deployment)).await;
            if let Err(status) = result {
                return Err(anyhow::anyhow!("{:?}", status));
            }
            Ok(result?.into_inner())
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<(), anyhow::Error>")]
pub struct DeleteSwitch(pub Identifier);

impl Handler<DeleteSwitch> for SwitchClient {
    type Result = ResponseFuture<Result<()>>;

    fn handle(&mut self, msg: DeleteSwitch, _ctx: &mut Self::Context) -> Self::Result {
        let node_identifier = msg.0;
        let mut client = self.0.clone();
        Box::pin(async move {
            let result = client.delete(tonic::Request::new(node_identifier)).await;
            if let Err(status) = result {
                return Err(anyhow::anyhow!("{:?}", status));
            }
            Ok(())
        })
    }
}
