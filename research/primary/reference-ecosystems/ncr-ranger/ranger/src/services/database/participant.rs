use super::Database;
use crate::models::helpers::uuid::Uuid;
use crate::models::{Participant, NewParticipant};
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{Ok, Result};
use diesel::RunQueryDsl;



#[derive(Message)]
#[rtype(result = "Result<Participant>")]
pub struct CreateParticipant(pub NewParticipant);

impl Handler<CreateParticipant> for Database {
    type Result = ResponseActFuture<Self, Result<Participant>>;

    fn handle(&mut self, msg: CreateParticipant, _ctx: &mut Self::Context) -> Self::Result {
        let new_participant = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let participant = block(move || {
                    new_participant.create_insert().execute(&mut connection)?;
                    let participant = Participant::by_id(new_participant.id).first(&mut connection)?;

                    Ok(participant)
                })
                .await??;

                Ok(participant)
            }
            .into_actor(self),
        )
    }
}


#[derive(Message)]
#[rtype(result = "Result<Vec<Participant>>")]
pub struct GetParticipants(pub Uuid);

impl Handler<GetParticipants> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<Participant>>>;

    fn handle(&mut self, msg: GetParticipants, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let deployment_uuid = msg.0;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let participant = block(move || {
                    let participant = Participant::by_deployment_id(deployment_uuid).load(&mut connection)?;

                    Ok(participant)
                })
                .await??;

                Ok(participant)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Uuid>")]

pub struct DeleteParticipant(pub Uuid);
impl Handler<DeleteParticipant> for Database {
    type Result = ResponseActFuture<Self, Result<Uuid>>;

    fn handle(&mut self, msg: DeleteParticipant, _ctx: &mut Self::Context) -> Self::Result {
        let id = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let id = block(move || {
                    let participant = Participant::by_id(id).first(&mut connection)?;
                    participant.soft_delete().execute(&mut connection)?;

                    Ok(id)
                })
                .await??;

                Ok(id)
            }
            .into_actor(self),
        )
    }
}