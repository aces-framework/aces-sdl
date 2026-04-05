use super::Database;
use crate::models::helpers::uuid::Uuid;
use crate::models::{ConditionMessage, NewConditionMessage, Score};
use crate::services::websocket::SocketScoring;
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use diesel::RunQueryDsl;
use sdl_parser::metric::Metric;

#[derive(Message)]
#[rtype(result = "Result<ConditionMessage>")]
pub struct CreateConditionMessage(
    pub NewConditionMessage,
    pub Option<(String, Metric)>,
    pub String,
);

impl Handler<CreateConditionMessage> for Database {
    type Result = ResponseActFuture<Self, Result<ConditionMessage>>;

    fn handle(&mut self, msg: CreateConditionMessage, _ctx: &mut Self::Context) -> Self::Result {
        let new_condition_message = msg.0;
        let metric = msg.1;
        let vm_name = msg.2;
        let connection_result = self.get_shared_connection();
        let websocket_manager = self.websocket_manager_address.clone();

        Box::pin(
            async move {
                let condition_message = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;

                    new_condition_message
                        .create_insert()
                        .execute(&mut *connection)?;

                    let condition_message = ConditionMessage::by_id(new_condition_message.id)
                        .first(&mut *connection)?;

                    if let Some(metric) = metric {
                        let score: Score = Score::from_conditionmessage_and_metric(
                            condition_message.clone(),
                            metric,
                            vm_name,
                        );
                        let scoring_msg = SocketScoring(
                            score.exercise_id,
                            (score.id, score.exercise_id, score).into(),
                        );
                        websocket_manager.do_send(scoring_msg);
                    }

                    Ok(condition_message)
                })
                .await??;

                Ok(condition_message)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<ConditionMessage>")]
pub struct GetConditionMessage(pub Uuid);

impl Handler<GetConditionMessage> for Database {
    type Result = ResponseActFuture<Self, Result<ConditionMessage>>;

    fn handle(&mut self, msg: GetConditionMessage, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let id = msg.0;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let condition_message = block(move || {
                    let condition_message = ConditionMessage::by_id(id).first(&mut connection)?;

                    Ok(condition_message)
                })
                .await??;

                Ok(condition_message)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<ConditionMessage>>")]
pub struct GetConditionMessagesByDeploymentId(pub Uuid);

impl Handler<GetConditionMessagesByDeploymentId> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<ConditionMessage>>>;

    fn handle(
        &mut self,
        msg: GetConditionMessagesByDeploymentId,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let connection_result = self.get_connection();
        let id = msg.0;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let condition_messages = block(move || {
                    let condition_messages =
                        ConditionMessage::by_deployment_id(id).load(&mut connection)?;

                    Ok(condition_messages)
                })
                .await??;

                Ok(condition_messages)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<ConditionMessage>>")]
pub struct GetConditionMessagesByExerciseId(pub Uuid);

impl Handler<GetConditionMessagesByExerciseId> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<ConditionMessage>>>;

    fn handle(
        &mut self,
        msg: GetConditionMessagesByExerciseId,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let connection_result = self.get_connection();
        let id = msg.0;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let condition_messages = block(move || {
                    let condition_messages =
                        ConditionMessage::by_exercise_id(id).load(&mut connection)?;

                    Ok(condition_messages)
                })
                .await??;

                Ok(condition_messages)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Uuid>")]
pub struct DeleteConditionMessage(pub Uuid);

impl Handler<DeleteConditionMessage> for Database {
    type Result = ResponseActFuture<Self, Result<Uuid>>;

    fn handle(&mut self, msg: DeleteConditionMessage, _ctx: &mut Self::Context) -> Self::Result {
        let id = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let id = block(move || {
                    let condition_message = ConditionMessage::by_id(id).first(&mut connection)?;
                    condition_message.soft_delete().execute(&mut connection)?;

                    Ok(id)
                })
                .await??;

                Ok(id)
            }
            .into_actor(self),
        )
    }
}
