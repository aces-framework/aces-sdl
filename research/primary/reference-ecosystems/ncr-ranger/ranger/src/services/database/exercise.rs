use super::Database;
use crate::constants::RECORD_NOT_FOUND;
use crate::models::helpers::uuid::Uuid;
use crate::models::{Exercise, NewExercise};
use crate::services::websocket::SocketExerciseUpdate;
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use diesel::RunQueryDsl;

#[derive(Message)]
#[rtype(result = "Result<Exercise>")]
pub struct CreateExercise(pub NewExercise);

impl Handler<CreateExercise> for Database {
    type Result = ResponseActFuture<Self, Result<Exercise>>;

    fn handle(&mut self, msg: CreateExercise, _ctx: &mut Self::Context) -> Self::Result {
        let new_exercise = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let exercise = block(move || {
                    new_exercise.create_insert().execute(&mut connection)?;
                    let exercise = Exercise::by_id(new_exercise.id).first(&mut connection)?;

                    Ok(exercise)
                })
                .await??;

                Ok(exercise)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Exercise>")]
pub struct GetExercise(pub Uuid);

impl Handler<GetExercise> for Database {
    type Result = ResponseActFuture<Self, Result<Exercise>>;

    fn handle(&mut self, msg: GetExercise, _ctx: &mut Self::Context) -> Self::Result {
        let uuid = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let exercise = block(move || {
                    let exercise = Exercise::by_id(uuid).first(&mut connection)?;

                    Ok(exercise)
                })
                .await??;

                Ok(exercise)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<Exercise>>")]
pub struct GetExercises;

impl Handler<GetExercises> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<Exercise>>>;

    fn handle(&mut self, _: GetExercises, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_shared_connection();

        Box::pin(
            async move {
                let exercise = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let exercises = Exercise::all().load(&mut *connection)?;

                    Ok(exercises)
                })
                .await??;

                Ok(exercise)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Exercise>")]
pub struct UpdateExercise(pub Uuid, pub crate::models::UpdateExercise);

impl Handler<UpdateExercise> for Database {
    type Result = ResponseActFuture<Self, Result<Exercise>>;

    fn handle(&mut self, msg: UpdateExercise, _ctx: &mut Self::Context) -> Self::Result {
        let uuid = msg.0;
        let update_exercise = msg.1;
        let connection_result = self.get_connection();
        let websocket_manager = self.websocket_manager_address.clone();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let exercise = block(move || {
                    let updated_rows = update_exercise
                        .create_update(uuid)
                        .execute(&mut connection)?;
                    if updated_rows != 1 {
                        return Err(anyhow!(RECORD_NOT_FOUND));
                    }
                    let exercise = Exercise::by_id(uuid).first(&mut connection)?;
                    websocket_manager.do_send(SocketExerciseUpdate(
                        exercise.id,
                        (exercise.id, exercise.id, update_exercise).into(),
                    ));

                    Ok(exercise)
                })
                .await??;

                Ok(exercise)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Uuid>")]
pub struct DeleteExercise(pub Uuid);

impl Handler<DeleteExercise> for Database {
    type Result = ResponseActFuture<Self, Result<Uuid>>;

    fn handle(&mut self, msg: DeleteExercise, _ctx: &mut Self::Context) -> Self::Result {
        let id = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let id = block(move || {
                    let exercise = Exercise::by_id(id).first(&mut connection)?;
                    exercise.soft_delete().execute(&mut connection)?;

                    Ok(id)
                })
                .await??;

                Ok(id)
            }
            .into_actor(self),
        )
    }
}
