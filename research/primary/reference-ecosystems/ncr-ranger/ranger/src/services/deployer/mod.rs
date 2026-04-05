mod distribution;
mod factory;

use super::client::{
    ConditionClient, DeputyQueryClient, EventInfoClient, FeatureClient, InjectClient, SwitchClient,
    TemplateClient, VirtualMachineClient,
};
use actix::{Actor, Addr};
use anyhow::Result;
pub use distribution::*;
pub use factory::DeployerFactory;
use ranger_grpc::capabilities::DeployerType as GrpcDeployerType;

#[derive(Clone)]
pub struct DeployerConnections {
    virtual_machine_client: Option<Addr<VirtualMachineClient>>,
    switch_client: Option<Addr<SwitchClient>>,
    template_client: Option<Addr<TemplateClient>>,
    feature_client: Option<Addr<FeatureClient>>,
    condition_client: Option<Addr<ConditionClient>>,
    inject_client: Option<Addr<InjectClient>>,
    event_info_client: Option<Addr<EventInfoClient>>,
    deputy_query_client: Option<Addr<DeputyQueryClient>>,
}

impl DeployerConnections {
    pub async fn new(capabilities: Vec<GrpcDeployerType>, address: &str) -> Result<Self> {
        let mut virtual_machine_client = None;
        let mut template_client = None;
        let mut switch_client = None;
        let mut feature_client = None;
        let mut condition_client = None;
        let mut inject_client = None;
        let mut event_info_client = None;
        let mut deputy_query_client = None;

        if capabilities.contains(&GrpcDeployerType::VirtualMachine) {
            virtual_machine_client = Some(
                VirtualMachineClient::new(address.to_string())
                    .await?
                    .start(),
            );
        }
        if capabilities.contains(&GrpcDeployerType::Template) {
            template_client = Some(TemplateClient::new(address.to_string()).await?.start());
        }
        if capabilities.contains(&GrpcDeployerType::Switch) {
            switch_client = Some(SwitchClient::new(address.to_string()).await?.start());
        }
        if capabilities.contains(&GrpcDeployerType::Feature) {
            feature_client = Some(FeatureClient::new(address.to_string()).await?.start());
        }
        if capabilities.contains(&GrpcDeployerType::Condition) {
            condition_client = Some(ConditionClient::new(address.to_string()).await?.start());
        }
        if capabilities.contains(&GrpcDeployerType::Inject) {
            inject_client = Some(InjectClient::new(address.to_string()).await?.start());
        }
        if capabilities.contains(&GrpcDeployerType::EventInfo) {
            event_info_client = Some(EventInfoClient::new(address.to_string()).await?.start());
        }
        if capabilities.contains(&GrpcDeployerType::DeputyQuery) {
            deputy_query_client = Some(DeputyQueryClient::new(address.to_string()).await?.start());
        }
        Ok(Self {
            virtual_machine_client,
            switch_client,
            template_client,
            feature_client,
            condition_client,
            inject_client,
            event_info_client,
            deputy_query_client,
        })
    }
}
