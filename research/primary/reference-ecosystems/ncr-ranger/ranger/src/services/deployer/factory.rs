use crate::configuration::AddressBook;

use super::DeployerConnections;
use actix::{Actor, Context, Handler, Message, ResponseActFuture, WrapFuture};
use anyhow::{anyhow, Ok, Result};
use futures::future::try_join_all;
use ranger_grpc::{capabilities::DeployerType as GrpcDeployerType, capability_client::CapabilityClient, Capabilities};
use std::collections::HashMap;
use tonic::transport::Channel;
type CapabilityClients = HashMap<String, CapabilityClient<Channel>>;

pub struct DeployerFactory {
    capability_clients: CapabilityClients,
    deployer_addresses: AddressBook,
}

impl Actor for DeployerFactory {
    type Context = Context<Self>;
}

impl DeployerFactory {
    async fn get_client(
        client_map: &CapabilityClients,
        deployer_name: &str,
    ) -> Result<CapabilityClient<Channel>> {
        let client = client_map
            .get(deployer_name)
            .ok_or_else(|| anyhow!("No capability client found for deployer"))?
            .clone();
        Ok(client)
    }

    async fn get_capabilities(mut client: CapabilityClient<Channel>) -> Result<Vec<GrpcDeployerType>> {
        let result = client.get_capabilities(tonic::Request::new(())).await;
        if let Err(status) = result {
            return Err(anyhow!("{:?}", status));
        }

        let result = client.get_capabilities(tonic::Request::new(())).await;
        if let Err(status) = result {
            return Err(anyhow!(
                "Failed to get capabilities with gRPC status {:?}",
                status
            ));
        }
        let capabilities: Capabilities = result?.into_inner();
        let deployment_types: Vec<GrpcDeployerType> = capabilities.values().collect();
        Ok(deployment_types)
    }

    pub async fn new(deployers_map: &AddressBook) -> Result<Self> {
        let capability_clients = try_join_all(deployers_map.iter().map(
            |(deployer_name, deployer_address)| async {
                Ok::<(String, CapabilityClient<Channel>)>((
                    deployer_name.clone(),
                    CapabilityClient::connect(deployer_address.to_string()).await?,
                ))
            },
        ))
        .await?
        .into_iter()
        .collect();

        Ok(Self {
            capability_clients,
            deployer_addresses: deployers_map.clone(),
        })
    }
}

#[derive(Message, Debug)]
#[rtype(result = "Result<DeployerConnections, anyhow::Error>")]
pub struct CreateDeployer(pub String);

impl Handler<CreateDeployer> for DeployerFactory {
    type Result = ResponseActFuture<Self, Result<DeployerConnections>>;

    fn handle(&mut self, msg: CreateDeployer, _ctx: &mut Self::Context) -> Self::Result {
        let capability_clients = self.capability_clients.clone();
        let deployer_addresses = self.deployer_addresses.clone();
        let deployer_name = msg.0;
        Box::pin(
            async move {
                let client = Self::get_client(&capability_clients, &deployer_name).await?;
                let capabilities = Self::get_capabilities(client).await?;
                let address = deployer_addresses.get(&deployer_name).unwrap();
                Ok(DeployerConnections::new(capabilities, address).await?)
            }
            .into_actor(self),
        )
    }
}
