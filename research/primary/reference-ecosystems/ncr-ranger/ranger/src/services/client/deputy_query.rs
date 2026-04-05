use super::DeputyQueryDeploymentClient;
use crate::services::client::DeploymentInfo;
use actix::{Actor, Addr, Context, Handler, Message, ResponseFuture};
use anyhow::{Ok, Result};
use async_trait::async_trait;
use ranger_grpc::{
    deputy_query_service_client::DeputyQueryServiceClient, GetPackagesQuery, GetPackagesResponse,
    Package, Source,
};
use ranger_grpc::{DeputyCreateResponse, DeputyStreamResponse, GetScenarioResponse, Identifier};
use tonic::transport::Channel;
use tonic::Streaming;

pub struct DeputyQueryClient {
    deputy_query_client: DeputyQueryServiceClient<Channel>,
}

impl DeputyQueryClient {
    pub async fn new(server_address: String) -> Result<Self> {
        Ok(Self {
            deputy_query_client: DeputyQueryServiceClient::connect(server_address).await?,
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<DeputyCreateResponse>")]
pub struct CreateBanner(pub Source);

impl Handler<CreateBanner> for DeputyQueryClient {
    type Result = ResponseFuture<Result<DeputyCreateResponse>>;

    fn handle(&mut self, msg: CreateBanner, _ctx: &mut Self::Context) -> Self::Result {
        let create_banner = msg.0;
        let mut client = self.deputy_query_client.clone();

        Box::pin(async move {
            let result = client.create(tonic::Request::new(create_banner)).await?;
            Ok(result.into_inner())
        })
    }
}

impl Actor for DeputyQueryClient {
    type Context = Context<Self>;
}

#[derive(Message)]
#[rtype(result = "Result<GetPackagesResponse>")]
pub struct GetDeputyPackages(pub GetPackagesQuery);

impl Handler<GetDeputyPackages> for DeputyQueryClient {
    type Result = ResponseFuture<Result<GetPackagesResponse>>;

    fn handle(&mut self, msg: GetDeputyPackages, _ctx: &mut Self::Context) -> Self::Result {
        let get_packages_query = msg.0;
        let mut client = self.deputy_query_client.clone();

        Box::pin(async move {
            let result = client
                .get_packages_by_type(tonic::Request::new(get_packages_query))
                .await?;
            Ok(result.into_inner())
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<GetScenarioResponse>")]
pub struct GetScenario(pub Source);

impl Handler<GetScenario> for DeputyQueryClient {
    type Result = ResponseFuture<Result<GetScenarioResponse>>;

    fn handle(&mut self, msg: GetScenario, _ctx: &mut Self::Context) -> Self::Result {
        let get_scenario_query = msg.0;
        let mut client = self.deputy_query_client.clone();

        Box::pin(async move {
            let result = client
                .get_scenario(tonic::Request::new(get_scenario_query))
                .await?;
            Ok(result.into_inner())
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<Streaming<DeputyStreamResponse>>")]
pub struct GetBannerFile(pub Identifier);

impl Handler<GetBannerFile> for DeputyQueryClient {
    type Result = ResponseFuture<Result<Streaming<DeputyStreamResponse>>>;

    fn handle(&mut self, msg: GetBannerFile, _ctx: &mut Self::Context) -> Self::Result {
        let identifier = msg.0;
        let mut client = self.deputy_query_client.clone();
        Box::pin(async move {
            let result = client.stream(identifier).await?;
            Ok(result.into_inner())
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct CheckPackageExists(pub Source);

impl Handler<CheckPackageExists> for DeputyQueryClient {
    type Result = ResponseFuture<Result<()>>;

    fn handle(&mut self, msg: CheckPackageExists, _ctx: &mut Self::Context) -> Self::Result {
        let check_package_exists_query = msg.0;
        let mut client = self.deputy_query_client.clone();

        Box::pin(async move {
            let result = client
                .check_package_exists(tonic::Request::new(check_package_exists_query))
                .await?;
            result.into_inner();
            Ok(())
        })
    }
}

#[async_trait]
impl DeputyQueryDeploymentClient for Addr<DeputyQueryClient> {
    async fn packages_query_by_type(&mut self, package_type: String) -> Result<Vec<Package>> {
        let query_result = self
            .send(GetDeputyPackages(GetPackagesQuery {
                package_type: package_type.clone(),
            }))
            .await??;
        Ok(query_result.packages)
    }

    async fn get_exercise(&mut self, source: Source) -> Result<String> {
        let query_result = self.send(GetScenario(source)).await??;
        Ok(query_result.sdl)
    }

    async fn get_banner_file(&mut self, source: Source) -> Result<Streaming<DeputyStreamResponse>> {
        let banner = CreateBanner(source.as_any().downcast_ref::<Source>().unwrap().clone());
        let create_banner_response = self.send(banner).await??;
        let query_result = self
            .send(GetBannerFile(Identifier {
                value: create_banner_response.id,
            }))
            .await??;
        Ok(query_result)
    }

    async fn check_package_exists(&mut self, source: Source) -> Result<()> {
        let result = self.send(CheckPackageExists(source)).await??;
        Ok(result)
    }
}
