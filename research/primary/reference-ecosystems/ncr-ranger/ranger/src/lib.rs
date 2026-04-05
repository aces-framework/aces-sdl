pub(crate) mod configuration;
pub(crate) mod constants;
pub mod errors;
pub mod middleware;
pub mod models;
pub mod roles;
pub mod routes;
pub(crate) mod schema;
pub(crate) mod services;
pub(crate) mod utilities;

use crate::services::{database::Database, deployer::DeployerDistribution, scheduler::Scheduler};
use actix::{Actor, Addr};
use anyhow::Result;
use configuration::{read_configuration, Configuration};
use services::{
    deployer::DeployerFactory,
    deployment::{condition::ConditionAggregator, event::EventPoller, DeploymentManager},
    websocket::WebSocketManager,
};

mod logger;

#[derive(Debug, Clone)]
pub struct Addressor {
    pub scheduler: Addr<Scheduler>,
    pub distributor: Addr<DeployerDistribution>,
    pub database: Addr<Database>,
    pub condition_aggregator: Addr<ConditionAggregator>,
    pub event_poller: Addr<EventPoller>,
}

impl Addressor {
    pub async fn try_new(
        deployer_distributor: DeployerDistribution,
        database: Database,
    ) -> Result<Self> {
        let scheduler = Scheduler::new().start();
        let distributor = deployer_distributor.start();
        let condition_aggregator = ConditionAggregator::new().start();
        let database = database.start();
        let event_poller = EventPoller::new().start();

        Ok(Self {
            scheduler,
            distributor,
            database,
            condition_aggregator,
            event_poller,
        })
    }
}

pub struct AppState {
    pub database_address: Addr<Database>,
    pub configuration: Configuration,
    pub deployer_distributor_address: Addr<DeployerDistribution>,
    pub deployment_manager_address: Addr<DeploymentManager>,
    pub websocket_manager_address: Addr<WebSocketManager>,
}

impl AppState {
    pub fn new(
        configuration: &configuration::Configuration,
        addressor: &Addressor,
        websocket_manager: &Addr<WebSocketManager>,
    ) -> Self {
        AppState {
            database_address: addressor.database.clone(),
            deployer_distributor_address: addressor.distributor.clone(),
            deployment_manager_address: DeploymentManager::new(
                addressor.clone(),
                configuration.deployment_groups.clone(),
                configuration.default_deployment_group.to_string(),
            )
            .start(),
            configuration: configuration.to_owned(),
            websocket_manager_address: websocket_manager.clone(),
        }
    }
}

pub async fn app_setup(environment_arguments: Vec<String>) -> Result<(String, u16, AppState)> {
    let configuration = read_configuration(environment_arguments)?;
    let deployer_factory = DeployerFactory::new(&configuration.deployers)
        .await
        .unwrap_or_else(|error| panic!("Failed to create deployer distribution: {error}"))
        .start();

    let deployer_distributor = DeployerDistribution::new(
        deployer_factory,
        configuration.deployers.keys().cloned().collect(),
    )
    .await
    .unwrap_or_else(|error| panic!("Failed to create deployer distribution: {error}"));

    let websocket_manager = WebSocketManager::new().start();

    let database = Database::try_new(&configuration.database_url, &websocket_manager)
        .unwrap_or_else(|error| {
            panic!(
                "Failed to create database connection to {} due to: {error}",
                &configuration.database_url
            )
        });
    let logger_config = configuration.logger.as_deref().unwrap_or("ranger.log");
    let _ = logger::init(logger_config, websocket_manager.clone());
    let addressor = Addressor::try_new(deployer_distributor, database).await?;
    let app_state = AppState::new(&configuration, &addressor, &websocket_manager);
    Ok((configuration.host, configuration.port, app_state))
}
