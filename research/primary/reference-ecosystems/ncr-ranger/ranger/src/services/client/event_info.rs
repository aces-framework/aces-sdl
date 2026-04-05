use super::{DeploymentClient, DeploymentClientResponse, DeploymentInfo};
use actix::{Actor, Addr, Context, Handler, Message, ResponseFuture};
use anyhow::{Ok, Result};
use async_trait::async_trait;
use ranger_grpc::{
    deputy_query_service_client::DeputyQueryServiceClient, DeputyCreateResponse, DeputyStreamResponse,
    Identifier, Source as GrpcSource,
};
use tonic::{transport::Channel, Streaming};

pub struct EventInfoClient {
    event_info_client: DeputyQueryServiceClient<Channel>,
}

impl EventInfoClient {
    pub async fn new(server_address: String) -> Result<Self> {
        Ok(Self {
            event_info_client: DeputyQueryServiceClient::connect(server_address).await?,
        })
    }
}

impl Actor for EventInfoClient {
    type Context = Context<Self>;
}

#[async_trait]
impl DeploymentClient<Box<dyn DeploymentInfo>> for Addr<EventInfoClient> {
    async fn deploy(
        &mut self,
        deployment_struct: Box<dyn DeploymentInfo>,
    ) -> Result<DeploymentClientResponse> {
        let deployment = CreateEventInfo(
            deployment_struct
                .as_any()
                .downcast_ref::<GrpcSource>()
                .unwrap()
                .clone(),
        );
        let create_event_info_response = self.send(deployment).await??;
        let event_info_stream = self
            .send(CreateEventInfoStream(Identifier {
                value: create_event_info_response.id.to_owned(),
            }))
            .await??;
        Ok(DeploymentClientResponse::EventInfoResponse((
            create_event_info_response,
            event_info_stream,
        )))
    }

    async fn undeploy(&mut self, handler_reference: String) -> Result<()> {
        self.send(DeleteEventInfo(Identifier {
            value: handler_reference,
        }))
        .await??;

        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<DeputyCreateResponse>")]
pub struct CreateEventInfo(pub GrpcSource);

impl Handler<CreateEventInfo> for EventInfoClient {
    type Result = ResponseFuture<Result<DeputyCreateResponse>>;

    fn handle(&mut self, msg: CreateEventInfo, _ctx: &mut Self::Context) -> Self::Result {
        let create_event = msg.0;
        let mut client = self.event_info_client.clone();

        Box::pin(async move {
            let result = client.create(tonic::Request::new(create_event)).await?;
            Ok(result.into_inner())
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<Streaming<DeputyStreamResponse>>")]
pub struct CreateEventInfoStream(pub Identifier);

impl Handler<CreateEventInfoStream> for EventInfoClient {
    type Result = ResponseFuture<Result<Streaming<DeputyStreamResponse>>>;

    fn handle(&mut self, msg: CreateEventInfoStream, _ctx: &mut Self::Context) -> Self::Result {
        let identifier = msg.0;
        let mut client = self.event_info_client.clone();

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
pub struct DeleteEventInfo(pub Identifier);

impl Handler<DeleteEventInfo> for EventInfoClient {
    type Result = ResponseFuture<Result<()>>;

    fn handle(&mut self, msg: DeleteEventInfo, _ctx: &mut Self::Context) -> Self::Result {
        let identifier = msg.0;
        let mut client = self.event_info_client.clone();
        Box::pin(async move {
            let result = client.delete(tonic::Request::new(identifier)).await;
            if let Err(status) = result {
                return Err(anyhow::anyhow!("{:?}", status));
            }
            Ok(())
        })
    }
}
