use super::{DeploymentClient, DeploymentClientResponse, DeploymentInfo};
use actix::{Actor, Addr, Context, Handler, Message, ResponseFuture};
use anyhow::{Ok, Result};
use async_trait::async_trait;
use ranger_grpc::{
    virtual_machine_service_client::VirtualMachineServiceClient, DeployVirtualMachine, Identifier,
};
use std::any::Any;
use tonic::transport::Channel;

impl DeploymentInfo for DeployVirtualMachine {
    fn get_deployment(&self) -> DeployVirtualMachine {
        self.clone()
    }
    fn as_any(&self) -> &dyn Any {
        self
    }
}

#[async_trait]
impl DeploymentClient<Box<dyn DeploymentInfo>> for Addr<VirtualMachineClient> {
    async fn deploy(
        &mut self,
        deployment_struct: Box<dyn DeploymentInfo>,
    ) -> Result<DeploymentClientResponse> {
        let deployment = CreateVirtualMachine(
            deployment_struct
                .as_any()
                .downcast_ref::<DeployVirtualMachine>()
                .unwrap()
                .clone(),
        );
        let identifier = self.send(deployment).await??;

        Ok(DeploymentClientResponse::Identifier(identifier))
    }

    async fn undeploy(&mut self, handler_reference: String) -> Result<()> {
        let undeploy = DeleteVirtualMachine(Identifier {
            value: handler_reference,
        });
        self.send(undeploy).await??;

        Ok(())
    }
}

pub struct VirtualMachineClient(VirtualMachineServiceClient<Channel>);

impl Actor for VirtualMachineClient {
    type Context = Context<Self>;
}

impl VirtualMachineClient {
    pub async fn new(server_address: String) -> Result<Self> {
        Ok(Self(
            VirtualMachineServiceClient::connect(server_address.clone()).await?,
        ))
    }
}

#[derive(Message)]
#[rtype(result = "Result<Identifier, anyhow::Error>")]
pub struct CreateVirtualMachine(pub DeployVirtualMachine);

impl Handler<CreateVirtualMachine> for VirtualMachineClient {
    type Result = ResponseFuture<Result<Identifier>>;

    fn handle(&mut self, msg: CreateVirtualMachine, _ctx: &mut Self::Context) -> Self::Result {
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
pub struct DeleteVirtualMachine(pub Identifier);

impl Handler<DeleteVirtualMachine> for VirtualMachineClient {
    type Result = ResponseFuture<Result<()>>;

    fn handle(&mut self, msg: DeleteVirtualMachine, _ctx: &mut Self::Context) -> Self::Result {
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
