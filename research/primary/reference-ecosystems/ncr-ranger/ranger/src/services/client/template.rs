use super::{DeploymentClientResponse, DeploymentInfo};
use crate::services::client::DeploymentClient;
use actix::{Actor, Addr, Context, Handler, Message, ResponseFuture};
use anyhow::{Ok, Result};
use async_trait::async_trait;
use ranger_grpc::{
    template_service_client::TemplateServiceClient, Identifier, Source as GrpcSource,
    TemplateResponse,
};
use std::any::Any;
use tonic::transport::Channel;

impl DeploymentInfo for GrpcSource {
    fn get_deployment(&self) -> GrpcSource {
        self.clone()
    }
    fn as_any(&self) -> &dyn Any {
        self
    }
}

pub struct TemplateClient {
    template_client: TemplateServiceClient<Channel>,
}

impl TemplateClient {
    pub async fn new(server_address: String) -> Result<Self> {
        Ok(Self {
            template_client: TemplateServiceClient::connect(server_address.clone()).await?,
        })
    }
}

impl Actor for TemplateClient {
    type Context = Context<Self>;
}

#[async_trait]
impl DeploymentClient<Box<dyn DeploymentInfo>> for Addr<TemplateClient> {
    async fn deploy(
        &mut self,
        deployment_struct: Box<dyn DeploymentInfo>,
    ) -> Result<DeploymentClientResponse> {
        let deployment = CreateTemplate(
            deployment_struct
                .as_any()
                .downcast_ref::<GrpcSource>()
                .unwrap()
                .clone(),
        );
        let respose = self.send(deployment).await??;

        Ok(DeploymentClientResponse::TemplateResponse(respose))
    }

    async fn undeploy(&mut self, handler_reference: String) -> Result<()> {
        let undeploy = DeleteTemplate(Identifier {
            value: handler_reference,
        });
        self.send(undeploy).await??;

        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<TemplateResponse, anyhow::Error>")]
pub struct CreateTemplate(pub GrpcSource);

impl Handler<CreateTemplate> for TemplateClient {
    type Result = ResponseFuture<Result<TemplateResponse>>;

    fn handle(&mut self, msg: CreateTemplate, _ctx: &mut Self::Context) -> Self::Result {
        let template_deployment = msg.0;
        let mut client = self.template_client.clone();
        Box::pin(async move {
            let result = client
                .create(tonic::Request::new(template_deployment))
                .await?;
            Ok(result.into_inner())
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<(), anyhow::Error>")]
pub struct DeleteTemplate(pub Identifier);

impl Handler<DeleteTemplate> for TemplateClient {
    type Result = ResponseFuture<Result<()>>;

    fn handle(&mut self, msg: DeleteTemplate, _ctx: &mut Self::Context) -> Self::Result {
        let identifier = msg.0;
        let mut client = self.template_client.clone();
        Box::pin(async move {
            let result = client.delete(tonic::Request::new(identifier)).await;
            if let Err(status) = result {
                return Err(anyhow::anyhow!("{:?}", status));
            }
            Ok(())
        })
    }
}
