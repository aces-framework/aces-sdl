use super::Database;
use crate::models::{
    helpers::uuid::Uuid,
    upload::{Artifact, NewArtifact},
};
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{Ok, Result};
use diesel::RunQueryDsl;

#[derive(Message)]
#[rtype(result = "Result<Uuid>")]
pub struct UploadArtifact(pub NewArtifact);

impl Handler<UploadArtifact> for Database {
    type Result = ResponseActFuture<Self, Result<Uuid>>;

    fn handle(&mut self, msg: UploadArtifact, _ctx: &mut Self::Context) -> Self::Result {
        let new_file = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let upload_file = block(move || {
                    new_file
                        .create_insert_or_replace()
                        .execute(&mut connection)?;

                    Ok(new_file.id)
                })
                .await??;
                Ok(upload_file)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Artifact>")]
pub struct GetArtifactByMetricId(pub Uuid);

impl Handler<GetArtifactByMetricId> for Database {
    type Result = ResponseActFuture<Self, Result<Artifact>>;

    fn handle(&mut self, msg: GetArtifactByMetricId, _ctx: &mut Self::Context) -> Self::Result {
        let metric_id = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let artifact = block(move || {
                    let artifact = Artifact::by_metric_id(metric_id).first(&mut connection)?;
                    Ok(artifact)
                })
                .await??;
                Ok(artifact)
            }
            .into_actor(self),
        )
    }
}
