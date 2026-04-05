use super::Database;
use crate::models::event_info::{EventInfo, ExistsCheckResult, NewEventInfo};
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use diesel::{sql_query, sql_types::Text, RunQueryDsl};

#[derive(Message)]
#[rtype(result = "Result<EventInfo>")]
pub struct CreateEventInfo(pub NewEventInfo, pub bool);

impl Handler<CreateEventInfo> for Database {
    type Result = ResponseActFuture<Self, Result<EventInfo>>;

    fn handle(&mut self, msg: CreateEventInfo, _ctx: &mut Self::Context) -> Self::Result {
        let CreateEventInfo(new_event_info, use_shared_connection) = msg;
        let connection_result = self.pick_connection(use_shared_connection);

        Box::pin(
            async move {
                let event_info = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    new_event_info
                        .create_insert_or_ignore()
                        .execute(&mut *connection)?;
                    let event_info =
                        EventInfo::by_checksum(new_event_info.checksum).first(&mut *connection)?;

                    Ok(event_info)
                })
                .await??;

                Ok(event_info)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<EventInfo>")]
pub struct GetEventInfo(pub String, pub bool);

impl Handler<GetEventInfo> for Database {
    type Result = ResponseActFuture<Self, Result<EventInfo>>;

    fn handle(&mut self, msg: GetEventInfo, _ctx: &mut Self::Context) -> Self::Result {
        let GetEventInfo(cheksum, use_shared_connection) = msg;
        let connection_result = self.pick_connection(use_shared_connection);

        Box::pin(
            async move {
                let event_info = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    Ok(EventInfo::by_checksum(cheksum).first(&mut *connection)?)
                })
                .await??;

                Ok(event_info)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<String>")]
pub struct DeleteEventInfo(pub String, pub bool);
impl Handler<DeleteEventInfo> for Database {
    type Result = ResponseActFuture<Self, Result<String>>;

    fn handle(&mut self, msg: DeleteEventInfo, _ctx: &mut Self::Context) -> Self::Result {
        let DeleteEventInfo(checksum, use_shared_connection) = msg;
        let connection_result = self.pick_connection(use_shared_connection);

        Box::pin(
            async move {
                let checksum = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let event_info =
                        EventInfo::by_checksum(checksum.clone()).first(&mut *connection)?;
                    event_info.hard_delete().execute(&mut *connection)?;

                    Ok(checksum)
                })
                .await??;

                Ok(checksum)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<bool>")]
pub struct CheckEventInfo(pub String, pub bool);

impl Handler<CheckEventInfo> for Database {
    type Result = ResponseActFuture<Self, Result<bool>>;

    fn handle(&mut self, msg: CheckEventInfo, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.pick_connection(msg.1);
        let checksum = msg.0;
        Box::pin(
            async move {
                let mutex_connection = connection_result?;
                let mut connection = mutex_connection
                    .lock()
                    .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;

                let query = sql_query(
                    "SELECT EXISTS(SELECT 1 FROM event_info_data WHERE checksum = ?) as 'exists'",
                );
                let query = query.bind::<Text, _>(checksum);
                let exists = query.get_result::<ExistsCheckResult>(&mut *connection)?;

                Ok(exists.exists)
            }
            .into_actor(self),
        )
    }
}
