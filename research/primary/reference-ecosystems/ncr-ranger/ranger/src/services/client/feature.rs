use super::{DeploymentClient, DeploymentClientResponse, DeploymentInfo};
use actix::{Actor, Addr, Context, Handler, Message, ResponseFuture};
use anyhow::{Ok, Result};
use async_trait::async_trait;
use ranger_grpc::{
    feature_service_client::FeatureServiceClient, Feature as GrpcFeature, ExecutorResponse,
    Identifier,
};
use std::any::Any;
use tonic::transport::Channel;

impl DeploymentInfo for GrpcFeature {
    fn get_deployment(&self) -> GrpcFeature {
        self.clone()
    }
    fn as_any(&self) -> &dyn Any {
        self
    }
}
pub struct FeatureClient {
    feature_client: FeatureServiceClient<Channel>,
}

impl FeatureClient {
    pub async fn new(server_address: String) -> Result<Self> {
        Ok(Self {
            feature_client: FeatureServiceClient::connect(server_address).await?,
        })
    }
}

impl Actor for FeatureClient {
    type Context = Context<Self>;
}

#[async_trait]
impl DeploymentClient<Box<dyn DeploymentInfo>> for Addr<FeatureClient> {
    async fn deploy(
        &mut self,
        deployment_struct: Box<dyn DeploymentInfo>,
    ) -> Result<DeploymentClientResponse> {
        let deployment = CreateFeature(
            deployment_struct
                .as_any()
                .downcast_ref::<GrpcFeature>()
                .unwrap()
                .clone(),
        );
        let feature_response = self.send(deployment).await??;

        Ok(DeploymentClientResponse::ExecutorResponse(feature_response))
    }

    async fn undeploy(&mut self, handler_reference: String) -> Result<()> {
        let undeploy = DeleteFeature(Identifier {
            value: handler_reference,
        });
        self.send(undeploy).await??;

        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<ExecutorResponse>")]
pub struct CreateFeature(pub GrpcFeature);

impl Handler<CreateFeature> for FeatureClient {
    type Result = ResponseFuture<Result<ExecutorResponse>>;

    fn handle(&mut self, msg: CreateFeature, _ctx: &mut Self::Context) -> Self::Result {
        let feature_deployment = msg.0;
        let mut client = self.feature_client.clone();

        Box::pin(async move {
            let result = client
                .create(tonic::Request::new(feature_deployment))
                .await?;
            Ok(result.into_inner())
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct DeleteFeature(pub Identifier);

impl Handler<DeleteFeature> for FeatureClient {
    type Result = ResponseFuture<Result<()>>;

    fn handle(&mut self, msg: DeleteFeature, _ctx: &mut Self::Context) -> Self::Result {
        let identifier = msg.0;
        let mut client = self.feature_client.clone();
        Box::pin(async move {
            let result = client.delete(tonic::Request::new(identifier)).await;
            if let Err(status) = result {
                return Err(anyhow::anyhow!("{:?}", status));
            }
            Ok(())
        })
    }
}
