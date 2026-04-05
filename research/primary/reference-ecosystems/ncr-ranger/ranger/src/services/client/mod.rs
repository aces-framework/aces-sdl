mod condition;
mod deputy_query;
mod event_info;
mod feature;
mod inject;
mod switch;
mod template;
mod virtual_machine;

use anyhow::anyhow;
use anyhow::Result;
use async_trait::async_trait;
pub use condition::*;
pub use deputy_query::*;
pub use event_info::*;
pub use feature::*;
pub use inject::*;
use ranger_grpc::{
    ConditionStreamResponse, DeputyCreateResponse, DeputyStreamResponse, ExecutorResponse,
    Identifier, Package, Source, TemplateResponse,
};
use std::any::Any;
pub use switch::*;
pub use template::*;
use tonic::Streaming;
pub use virtual_machine::*;

pub type ConditionResponse = (Identifier, Streaming<ConditionStreamResponse>);
pub type EventInfoResponse = (DeputyCreateResponse, Streaming<DeputyStreamResponse>);
pub enum DeploymentClientResponse {
    Identifier(Identifier),
    ExecutorResponse(ExecutorResponse),
    TemplateResponse(TemplateResponse),
    ConditionResponse(ConditionResponse),
    EventInfoResponse(EventInfoResponse),
}

#[async_trait]
pub trait DeputyQueryDeploymentClient {
    async fn packages_query_by_type(&mut self, package_type: String) -> Result<Vec<Package>>;
    async fn get_exercise(&mut self, source: Source) -> Result<String>;
    async fn get_banner_file(&mut self, source: Source) -> Result<Streaming<DeputyStreamResponse>>;
    async fn check_package_exists(&mut self, source: Source) -> Result<()>;
}

#[async_trait]
pub trait DeploymentClient<T>
where
    T: Sized,
{
    async fn deploy(&mut self, deployment_struct: T) -> Result<DeploymentClientResponse>;
    async fn undeploy(&mut self, handler_reference: String) -> Result<()>;
}

pub trait DeploymentInfo
where
    Self: Send,
{
    fn get_deployment(&self) -> Self
    where
        Self: Sized;
    fn as_any(&self) -> &dyn Any;
}

pub trait Deployable {
    fn try_to_deployment_command(&self) -> Result<Box<dyn DeploymentInfo>>;
}

impl TryFrom<DeploymentClientResponse> for Identifier {
    type Error = anyhow::Error;

    fn try_from(client_response: DeploymentClientResponse) -> Result<Self> {
        match client_response {
            DeploymentClientResponse::Identifier(id) => Ok(id),
            _ => Err(anyhow!("Unable to convert ClientResponse into Identifier")),
        }
    }
}

impl TryFrom<DeploymentClientResponse> for ExecutorResponse {
    type Error = anyhow::Error;

    fn try_from(client_response: DeploymentClientResponse) -> Result<Self> {
        match client_response {
            DeploymentClientResponse::ExecutorResponse(executor_response) => Ok(executor_response),
            _ => Err(anyhow!(
                "Unable to convert ClientResponse into ExecutorResponse"
            )),
        }
    }
}

impl TryFrom<DeploymentClientResponse> for TemplateResponse {
    type Error = anyhow::Error;

    fn try_from(client_response: DeploymentClientResponse) -> Result<Self> {
        match client_response {
            DeploymentClientResponse::TemplateResponse(template_response) => Ok(template_response),
            _ => Err(anyhow!(
                "Unable to convert ClientResponse into TemplateResponse"
            )),
        }
    }
}

impl TryFrom<DeploymentClientResponse> for ConditionResponse {
    type Error = anyhow::Error;

    fn try_from(client_response: DeploymentClientResponse) -> Result<Self> {
        match client_response {
            DeploymentClientResponse::ConditionResponse((id, stream)) => Ok((id, stream)),
            _ => Err(anyhow!(
                "Unable to convert ClientResponse into ConditionResponse"
            )),
        }
    }
}

impl TryFrom<DeploymentClientResponse> for EventInfoResponse {
    type Error = anyhow::Error;

    fn try_from(client_response: DeploymentClientResponse) -> Result<Self> {
        match client_response {
            DeploymentClientResponse::EventInfoResponse((event_info, stream)) => {
                Ok((event_info, stream))
            }
            _ => Err(anyhow!(
                "Unable to convert ClientResponse into EventInfoResponse"
            )),
        }
    }
}
