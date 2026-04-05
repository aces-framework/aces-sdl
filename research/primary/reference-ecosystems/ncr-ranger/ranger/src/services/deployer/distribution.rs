use super::{
    super::client::{
        DeploymentClient, DeploymentInfo, SwitchClient, TemplateClient, VirtualMachineClient,
    },
    factory::{CreateDeployer, DeployerFactory},
};
use crate::services::{
    client::{
        ConditionClient, DeploymentClientResponse, DeputyQueryClient, DeputyQueryDeploymentClient,
        EventInfoClient, FeatureClient, InjectClient,
    },
    deployer::DeployerConnections,
};
use actix::{
    Actor, ActorFutureExt, Addr, Context, Handler, Message, ResponseActFuture, WrapFuture,
};
use anyhow::{anyhow, Ok, Result};
use futures::future::try_join_all;
use ranger_grpc::{
    capabilities::DeployerType as GrpcDeployerType, DeputyStreamResponse, Package, Source,
};
use std::collections::HashMap;
use tonic::Streaming;

#[derive(Clone)]
pub struct DeployerDistribution {
    deployers: HashMap<String, DeployerConnections>,
    usage: HashMap<String, usize>,
}

impl Actor for DeployerDistribution {
    type Context = Context<Self>;
}

type ClientTuple = (Box<dyn DeploymentClient<Box<dyn DeploymentInfo>>>, String);
type DeputyClientTuple = (Box<Addr<DeputyQueryClient>>, String);

impl DeployerDistribution {
    fn book_best_deployer(
        &mut self,
        potential_deployers: Vec<String>,
        deployer_type: GrpcDeployerType,
    ) -> Result<String> {
        let acceptable_deployers = self.deployers.iter().filter_map(|(key, value)| {
            if potential_deployers.contains(key)
                && (deployer_type == GrpcDeployerType::VirtualMachine
                    && value.virtual_machine_client.is_some()
                    || deployer_type == GrpcDeployerType::Switch && value.switch_client.is_some()
                    || deployer_type == GrpcDeployerType::Template
                        && value.template_client.is_some()
                    || deployer_type == GrpcDeployerType::Feature && value.feature_client.is_some()
                    || deployer_type == GrpcDeployerType::Condition
                        && value.condition_client.is_some()
                    || deployer_type == GrpcDeployerType::Inject && value.inject_client.is_some()
                    || deployer_type == GrpcDeployerType::EventInfo
                        && value.event_info_client.is_some()
                    || deployer_type == GrpcDeployerType::DeputyQuery
                        && value.deputy_query_client.is_some())
            {
                return Some(key.to_string());
            }
            None
        });

        let best_deployer = acceptable_deployers
            .into_iter()
            .min_by_key(|key| self.usage.get(key).unwrap_or(&0))
            .ok_or_else(|| anyhow!("No deployer found"))?;
        self.usage
            .entry(best_deployer.clone())
            .and_modify(|e| *e += 1)
            .or_insert(1);
        Ok(best_deployer)
    }

    fn release_deployer(&mut self, deployer_name: &str) {
        self.usage
            .entry(deployer_name.to_string())
            .and_modify(|e| *e -= 1)
            .or_insert(0);
    }

    fn release_deployer_closure<T>(
        response: Result<(T, String)>,
        actor: &mut DeployerDistribution,
        _ctx: &mut Context<DeployerDistribution>,
    ) -> Result<T> {
        let (value, deployer_name) = response?;
        actor.release_deployer(&deployer_name);
        Ok(value)
    }

    fn get_client(
        &mut self,
        potential_deployers: Vec<String>,
        deployer_type: GrpcDeployerType,
    ) -> Result<ClientTuple>
    where
        actix::Addr<VirtualMachineClient>: DeploymentClient<Box<dyn DeploymentInfo>>,
        actix::Addr<SwitchClient>: DeploymentClient<Box<dyn DeploymentInfo>>,
        actix::Addr<TemplateClient>: DeploymentClient<Box<dyn DeploymentInfo>>,
        actix::Addr<FeatureClient>: DeploymentClient<Box<dyn DeploymentInfo>>,
        actix::Addr<ConditionClient>: DeploymentClient<Box<dyn DeploymentInfo>>,
        actix::Addr<InjectClient>: DeploymentClient<Box<dyn DeploymentInfo>>,
        actix::Addr<EventInfoClient>: DeploymentClient<Box<dyn DeploymentInfo>>,
    {
        let best_deployer = self.book_best_deployer(potential_deployers, deployer_type)?;
        let connections = self
            .deployers
            .get(&best_deployer)
            .ok_or_else(|| anyhow!("No deployer found"))?;
        Ok((
            match deployer_type {
                GrpcDeployerType::Template => Box::new(
                    connections
                        .template_client
                        .clone()
                        .ok_or_else(|| anyhow!("No template deployer found"))?,
                ),
                GrpcDeployerType::Switch => Box::new(
                    connections
                        .switch_client
                        .clone()
                        .ok_or_else(|| anyhow!("No node deployer found"))?,
                ),
                GrpcDeployerType::VirtualMachine => Box::new(
                    connections
                        .virtual_machine_client
                        .clone()
                        .ok_or_else(|| anyhow!("No node deployer found"))?,
                ),
                GrpcDeployerType::Feature => Box::new(
                    connections
                        .feature_client
                        .clone()
                        .ok_or_else(|| anyhow!("No feature deployer found"))?,
                ),
                GrpcDeployerType::Inject => Box::new(
                    connections
                        .inject_client
                        .clone()
                        .ok_or_else(|| anyhow!("No inject deployer found"))?,
                ),
                GrpcDeployerType::Condition => Box::new(
                    connections
                        .condition_client
                        .clone()
                        .ok_or_else(|| anyhow!("No condition deployer found"))?,
                ),
                GrpcDeployerType::EventInfo => Box::new(
                    connections
                        .event_info_client
                        .clone()
                        .ok_or_else(|| anyhow!("No event info deployer found"))?,
                ),
                _ => return Err(anyhow!("Deployer type {:?} not supported", deployer_type)),
            },
            best_deployer,
        ))
    }

    fn get_deputy_query_client(
        &mut self,
        potential_deployers: Vec<String>,
    ) -> Result<DeputyClientTuple>
    where
        actix::Addr<DeputyQueryClient>: DeputyQueryDeploymentClient,
    {
        let best_deployer =
            self.book_best_deployer(potential_deployers, GrpcDeployerType::DeputyQuery)?;
        let connections = self
            .deployers
            .get(&best_deployer)
            .ok_or_else(|| anyhow!("No deployer found"))?;
        Ok((
            Box::new(
                connections
                    .deputy_query_client
                    .clone()
                    .ok_or_else(|| anyhow!("No deputy query deployer found"))?,
            ),
            best_deployer,
        ))
    }

    pub async fn new(factory: Addr<DeployerFactory>, deployers: Vec<String>) -> Result<Self> {
        let deployers = try_join_all(deployers.iter().map(|deployer_name| async {
            let connections = factory
                .send(CreateDeployer(deployer_name.to_string()))
                .await??;
            Ok((deployer_name.to_string(), connections))
        }))
        .await?;

        Ok(Self {
            deployers: HashMap::from_iter(deployers),
            usage: HashMap::new(),
        })
    }
}

#[derive(Message)]
#[rtype(result = "Result<DeploymentClientResponse>")]
pub struct Deploy(
    pub GrpcDeployerType,
    pub Box<dyn DeploymentInfo>,
    pub Vec<String>,
);

impl Handler<Deploy> for DeployerDistribution {
    type Result = ResponseActFuture<Self, Result<DeploymentClientResponse>>;

    fn handle(&mut self, msg: Deploy, _ctx: &mut Self::Context) -> Self::Result {
        let deployment_type = msg.0;
        let deployment = msg.1;
        let potential_deployers = msg.2;

        let client_result = self.get_client(potential_deployers, deployment_type);

        Box::pin(
            async move {
                let (mut deployment_client, best_deployer) = client_result?;
                let client_response = deployment_client.deploy(deployment).await?;

                Ok((client_response, best_deployer))
            }
            .into_actor(self)
            .map(Self::release_deployer_closure),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct UnDeploy(pub GrpcDeployerType, pub String, pub Vec<String>);

impl Handler<UnDeploy> for DeployerDistribution {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: UnDeploy, _ctx: &mut Self::Context) -> Self::Result {
        let deployment_type = msg.0;
        let handler_reference_id = msg.1;
        let potential_deployers = msg.2;

        let client_result = self.get_client(potential_deployers, deployment_type);

        Box::pin(
            async move {
                let (mut deployment_client, best_deployer) = client_result?;
                deployment_client.undeploy(handler_reference_id).await?;

                Ok(((), best_deployer))
            }
            .into_actor(self)
            .map(Self::release_deployer_closure),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<Package>>")]
pub struct DeputyPackageQueryByType(pub String, pub Vec<String>);

impl Handler<DeputyPackageQueryByType> for DeployerDistribution {
    type Result = ResponseActFuture<Self, Result<Vec<Package>>>;

    fn handle(&mut self, msg: DeputyPackageQueryByType, _ctx: &mut Self::Context) -> Self::Result {
        let package_type = msg.0;
        let potential_deployers = msg.1;

        let client_result = self.get_deputy_query_client(potential_deployers);

        Box::pin(
            async move {
                let (mut deployment_client, best_deployer) = client_result?;
                let query_result = deployment_client
                    .packages_query_by_type(package_type)
                    .await?;

                Ok((query_result, best_deployer))
            }
            .into_actor(self)
            .map(Self::release_deployer_closure),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<String>")]
pub struct DeputyPackageQueryGetExercise(pub Source, pub Vec<String>);

impl Handler<DeputyPackageQueryGetExercise> for DeployerDistribution {
    type Result = ResponseActFuture<Self, Result<String>>;

    fn handle(
        &mut self,
        msg: DeputyPackageQueryGetExercise,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let source = msg.0;
        let potential_deployers = msg.1;

        let client_result = self.get_deputy_query_client(potential_deployers);

        Box::pin(
            async move {
                let (mut deployment_client, best_deployer) = client_result?;
                let sdl = deployment_client.get_exercise(source).await?;

                Ok((sdl, best_deployer))
            }
            .into_actor(self)
            .map(Self::release_deployer_closure),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Streaming<DeputyStreamResponse>>")]
pub struct DeputyPackageQueryGetBannerFile(pub Source, pub Vec<String>);

impl Handler<DeputyPackageQueryGetBannerFile> for DeployerDistribution {
    type Result = ResponseActFuture<Self, Result<Streaming<DeputyStreamResponse>>>;

    fn handle(
        &mut self,
        msg: DeputyPackageQueryGetBannerFile,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let source = msg.0;
        let potential_deployers = msg.1;

        let client_result = self.get_deputy_query_client(potential_deployers);

        Box::pin(
            async move {
                let (mut deployment_client, best_deployer) = client_result?;
                let stream = deployment_client.get_banner_file(source).await?;
                Ok((stream, best_deployer))
            }
            .into_actor(self)
            .map(Self::release_deployer_closure),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct DeputyPackageQueryCheckPackageExists(pub Source, pub Vec<String>);
impl Handler<DeputyPackageQueryCheckPackageExists> for DeployerDistribution {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(
        &mut self,
        msg: DeputyPackageQueryCheckPackageExists,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let source = msg.0;
        let potential_deployers = msg.1;

        let client_result = self.get_deputy_query_client(potential_deployers);

        Box::pin(
            async move {
                let (mut deployment_client, best_deployer) = client_result?;
                deployment_client.check_package_exists(source).await?;
                Ok(((), best_deployer))
            }
            .into_actor(self)
            .map(Self::release_deployer_closure),
        )
    }
}
