use super::{DeploymentClient, DeploymentClientResponse, DeploymentInfo};
use actix::{Actor, Addr, Context, Handler, Message, ResponseFuture};
use anyhow::{Ok, Result};
use async_trait::async_trait;
use ranger_grpc::{inject_service_client::InjectServiceClient, Identifier, Inject as GrpcInject, ExecutorResponse};

use std::any::Any;
use tonic::transport::Channel;

impl DeploymentInfo for GrpcInject {
    fn get_deployment(&self) -> GrpcInject {
        self.clone()
    }
    fn as_any(&self) -> &dyn Any {
        self
    }
}
pub struct InjectClient {
    inject_client: InjectServiceClient<Channel>,
}

impl InjectClient {
    pub async fn new(server_address: String) -> Result<Self> {
        Ok(Self {
            inject_client: InjectServiceClient::connect(server_address).await?,
        })
    }
}

impl Actor for InjectClient {
    type Context = Context<Self>;
}

#[async_trait]
impl DeploymentClient<Box<dyn DeploymentInfo>> for Addr<InjectClient> {
    async fn deploy(
        &mut self,
        deployment_struct: Box<dyn DeploymentInfo>,
    ) -> Result<DeploymentClientResponse> {
        let deployment = CreateInject(
            deployment_struct
                .as_any()
                .downcast_ref::<GrpcInject>()
                .unwrap()
                .clone(),
        );
        let injector_response = self.send(deployment).await??;

        Ok(DeploymentClientResponse::ExecutorResponse(injector_response))
    }

    async fn undeploy(&mut self, handler_reference: String) -> Result<()> {
        let undeploy = DeleteInject(Identifier {
            value: handler_reference,
        });
        self.send(undeploy).await??;

        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<ExecutorResponse>")]
pub struct CreateInject(pub GrpcInject);

impl Handler<CreateInject> for InjectClient {
    type Result = ResponseFuture<Result<ExecutorResponse>>;

    fn handle(&mut self, msg: CreateInject, _ctx: &mut Self::Context) -> Self::Result {
        let inject_deployment = msg.0;
        let mut client = self.inject_client.clone();

        Box::pin(async move {
            let result = client
                .create(tonic::Request::new(inject_deployment))
                .await?;
            Ok(result.into_inner())
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct DeleteInject(pub Identifier);

impl Handler<DeleteInject> for InjectClient {
    type Result = ResponseFuture<Result<()>>;

    fn handle(&mut self, msg: DeleteInject, _ctx: &mut Self::Context) -> Self::Result {
        let identifier = msg.0;
        let mut client = self.inject_client.clone();
        Box::pin(async move {
            let result = client.delete(tonic::Request::new(identifier)).await;
            if let Err(status) = result {
                return Err(anyhow::anyhow!("{:?}", status));
            }
            Ok(())
        })
    }
}
