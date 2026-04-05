use super::Database;
use crate::constants::RECORD_NOT_FOUND;
use crate::models::helpers::uuid::Uuid;
use crate::models::Deployment;
use crate::models::Event;
use crate::models::NewEvent;
use crate::services::websocket::SocketEvent;
use crate::utilities::event::calculate_event_start_end_times;
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use chrono::NaiveDateTime;
use diesel::RunQueryDsl;
use sdl_parser::{event::Event as SdlEvent, Scenario};

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct CreateEvents;

#[derive(Message)]
#[rtype(result = "Result<Event>")]
pub struct CreateEvent {
    pub id: Uuid,
    pub name: String,
    pub exercise_id: Uuid,
    pub deployment_id: Uuid,
    pub description: Option<String>,
    pub start: NaiveDateTime,
    pub end: NaiveDateTime,
    pub use_shared_connection: bool,
}

impl CreateEvent {
    pub fn new(
        event_key: &str,
        event: &SdlEvent,
        deployment: &Deployment,
        scenario: &Scenario,
        deployment_id: Uuid,
    ) -> Result<Self> {
        let (event_start, event_end) =
            calculate_event_start_end_times(scenario, event_key, deployment.start, deployment.end)?;

        let new_event = CreateEvent {
            id: Uuid::random(),
            name: event_key.to_owned(),
            exercise_id: deployment.exercise_id,
            deployment_id,
            description: event.description.clone(),
            start: event_start,
            end: event_end,
            use_shared_connection: true,
        };

        Ok(new_event)
    }
}

impl Handler<CreateEvent> for Database {
    type Result = ResponseActFuture<Self, Result<Event>>;

    fn handle(&mut self, msg: CreateEvent, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.pick_connection(msg.use_shared_connection);
        let websocket_manager = self.websocket_manager_address.clone();

        Box::pin(
            async move {
                let exercise_id = msg.exercise_id;
                let new_event: NewEvent = msg.into();

                let mutex_connection = &connection_result?;
                let mut connection = mutex_connection
                    .lock()
                    .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                new_event
                    .create_insert_or_ignore()
                    .execute(&mut *connection)?;

                let event = Event::by_id(new_event.id).first(&mut *connection)?;
                let event_msg =
                    SocketEvent(exercise_id, (exercise_id, event.id, event.clone()).into());
                websocket_manager.do_send(event_msg);

                Ok(event)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Event>")]
pub struct GetEvent(pub Uuid);

impl Handler<GetEvent> for Database {
    type Result = ResponseActFuture<Self, Result<Event>>;

    fn handle(&mut self, msg: GetEvent, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let event_id = msg.0;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let event = block(move || {
                    let event = Event::by_id(event_id).first(&mut connection)?;

                    Ok(event)
                })
                .await??;

                Ok(event)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<Event>>")]
pub struct GetEventsByDeploymentId(pub Uuid);

impl Handler<GetEventsByDeploymentId> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<Event>>>;

    fn handle(&mut self, msg: GetEventsByDeploymentId, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let event_id = msg.0;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let events = block(move || {
                    let events = Event::by_deployment_id(event_id).load(&mut connection)?;

                    Ok(events)
                })
                .await??;

                Ok(events)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Event>")]
pub struct UpdateEvent(pub Uuid, pub Uuid, pub crate::models::UpdateEvent);

impl Handler<UpdateEvent> for Database {
    type Result = ResponseActFuture<Self, Result<Event>>;

    fn handle(&mut self, msg: UpdateEvent, _ctx: &mut Self::Context) -> Self::Result {
        let UpdateEvent(exercise_id, event_uuid, update_event) = msg;
        let connection_result = self.get_connection();
        let websocket_manager = self.websocket_manager_address.clone();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let event = block(move || {
                    let updated_rows = update_event
                        .create_update(event_uuid)
                        .execute(&mut connection)?;
                    if updated_rows != 1 {
                        return Err(anyhow!(RECORD_NOT_FOUND));
                    }
                    let event = Event::by_id(event_uuid).first(&mut connection)?;
                    let event_msg =
                        SocketEvent(exercise_id, (exercise_id, event.id, event.clone()).into());
                    websocket_manager.do_send(event_msg);

                    Ok(event)
                })
                .await??;

                Ok(event)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Event>")]
pub struct UpdateEventChecksum(pub Uuid, pub crate::models::UpdateEventChecksum);

impl Handler<UpdateEventChecksum> for Database {
    type Result = ResponseActFuture<Self, Result<Event>>;

    fn handle(&mut self, msg: UpdateEventChecksum, _ctx: &mut Self::Context) -> Self::Result {
        let uuid = msg.0;
        let update_event = msg.1;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let event = block(move || {
                    let updated_rows = update_event.create_update(uuid).execute(&mut connection)?;
                    if updated_rows != 1 {
                        return Err(anyhow!(RECORD_NOT_FOUND));
                    }
                    let event = Event::by_id(uuid).first(&mut connection)?;

                    Ok(event)
                })
                .await??;

                Ok(event)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Uuid>")]
pub struct DeleteEvent(pub Uuid);

impl Handler<DeleteEvent> for Database {
    type Result = ResponseActFuture<Self, Result<Uuid>>;

    fn handle(&mut self, msg: DeleteEvent, _ctx: &mut Self::Context) -> Self::Result {
        let id = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let id = block(move || {
                    let event = Event::by_id(id).first(&mut connection)?;
                    event.soft_delete().execute(&mut connection)?;

                    Ok(id)
                })
                .await??;

                Ok(id)
            }
            .into_actor(self),
        )
    }
}
