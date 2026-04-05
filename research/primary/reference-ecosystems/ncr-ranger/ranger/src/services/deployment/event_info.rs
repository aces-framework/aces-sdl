use crate::{
    models::{event_info::NewEventInfo, helpers::uuid::Uuid},
    services::{
        client::EventInfoResponse,
        database::{
            event::UpdateEventChecksum,
            event_info::{CheckEventInfo, CreateEventInfo},
            Database,
        },
        deployer::Deploy,
    },
    Addressor,
};
use actix::Addr;
use anyhow::{anyhow, Ok, Result};
use async_trait::async_trait;
use log::{debug, error};
use ranger_grpc::capabilities::DeployerType as GrpcDeployerType;
use ranger_grpc::Source as GrpcSource;
use sdl_parser::Scenario;
use sha3::{Digest, Sha3_256};

use super::event::DeploymentEvent;

async fn update_event_checksum(
    database_address: &Addr<Database>,
    event_info_checksum: String,
    event_id: Uuid,
) -> Result<()> {
    database_address
        .send(UpdateEventChecksum(
            event_id,
            crate::models::UpdateEventChecksum {
                event_info_data_checksum: Some(event_info_checksum.clone()),
            },
        ))
        .await??;

    Ok(())
}

#[async_trait]
pub trait EventInfoUnpacker {
    async fn create_event_info_pages(
        &self,
        addressor: &Addressor,
        deployers: &[String],
        deployment_events: &[DeploymentEvent],
    ) -> Result<()>;
}

#[async_trait]
impl EventInfoUnpacker for Scenario {
    async fn create_event_info_pages(
        &self,
        addressor: &Addressor,
        deployers: &[String],
        deployment_events: &[DeploymentEvent],
    ) -> Result<()> {
        for event in deployment_events {
            if let Some(event_source) = &event.sdl_event.source {
                let grpc_source = Box::new(GrpcSource {
                    name: event_source.name.to_owned(),
                    version: event_source.version.to_owned(),
                });

                match addressor
                    .distributor
                    .send(Deploy(
                        GrpcDeployerType::EventInfo,
                        grpc_source,
                        deployers.to_owned(),
                    ))
                    .await?
                {
                    Result::Ok(handler_response) => {
                        let (event_create_response, mut event_file_stream) =
                            EventInfoResponse::try_from(handler_response)?;

                        update_event_checksum(
                            &addressor.database,
                            event_create_response.checksum.clone(),
                            event.id,
                        )
                        .await?;

                        let event_info_file_already_exists = addressor
                            .database
                            .send(CheckEventInfo(event_create_response.checksum.clone(), true))
                            .await??;
                        if event_info_file_already_exists {
                            debug!("Event already exists in the database, skipping download step");
                            continue;
                        }

                        let mut event_file_buffer = Vec::new();
                        while let Some(stream_response) = event_file_stream.message().await? {
                            event_file_buffer.extend_from_slice(&stream_response.chunk);
                        }

                        let mut hasher = Sha3_256::new();
                        hasher.update(&event_file_buffer);
                        let computed_checksum = format!("{:x}", hasher.finalize());
                        if computed_checksum == event_create_response.checksum {
                            debug!(
                                "Event {event_name} info file Checksum verification passed",
                                event_name = event_source.name
                            );
                            addressor
                                .database
                                .send(CreateEventInfo(
                                    NewEventInfo {
                                        checksum: event_create_response.checksum,
                                        name: event_source.name.clone(),
                                        file_name: event_create_response.filename,
                                        file_size: event_create_response.size as u64,
                                        content: event_file_buffer,
                                    },
                                    true,
                                ))
                                .await??;
                        } else {
                            error!(
                                "Checksum verification for EventInfo file failed for event {event_name}, version {event_version}",
                                event_name = event_source.name, event_version = event_source.version
                            );
                            return Err(anyhow!("Checksum verification for EventInfo file failed"));
                        }
                        Ok(())
                    }
                    Result::Err(error) => return Err(anyhow!("Event info error: {error}")),
                }?;
            }
        }

        Ok(())
    }
}
