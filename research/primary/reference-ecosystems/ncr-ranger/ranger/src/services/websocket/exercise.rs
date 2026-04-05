use super::{RegisterExerciseSocket, UnRegisterExercise, WebSocketManager, WebsocketStringMessage};
use crate::models::helpers::uuid::Uuid;
use actix::{
    fut::ready, Actor, ActorContext, ActorFutureExt, Addr, AsyncContext, ContextFutureSpawner,
    Handler, Running, StreamHandler, WrapFuture,
};
use actix_web_actors::ws;

#[derive(Clone)]
pub struct ExerciseWebsocket {
    pub exercise_uuid: Uuid,
    pub recipient_id: Uuid,
    pub manager_address: Addr<WebSocketManager>,
}

impl ExerciseWebsocket {
    pub fn new(exercise_uuid: Uuid, websocket_manager_address: Addr<WebSocketManager>) -> Self {
        Self {
            exercise_uuid,
            recipient_id: Uuid::random(),
            manager_address: websocket_manager_address,
        }
    }
}

impl Actor for ExerciseWebsocket {
    type Context = ws::WebsocketContext<Self>;

    fn started(&mut self, ctx: &mut Self::Context) {
        let addr = ctx.address();
        self.manager_address
            .send(RegisterExerciseSocket(
                self.exercise_uuid,
                self.recipient_id,
                addr.recipient(),
            ))
            .into_actor(self)
            .then(|res, _, ctx| {
                if let Err(error) = res {
                    log::error!("Failed to register exercise websocket: {}", error);
                    ctx.stop();
                }
                ready(())
            })
            .wait(ctx);
    }

    fn stopping(&mut self, _: &mut Self::Context) -> Running {
        self.manager_address
            .do_send(UnRegisterExercise(self.exercise_uuid, self.recipient_id));
        Running::Stop
    }
}

impl StreamHandler<Result<ws::Message, ws::ProtocolError>> for ExerciseWebsocket {
    fn handle(
        &mut self,
        websocket_message: Result<ws::Message, ws::ProtocolError>,
        ctx: &mut Self::Context,
    ) {
        log::debug!("Received websocket message: {:?}", websocket_message);
        let websocket_message = match websocket_message {
            Err(error) => {
                log::error!("Failed to receive websocket message: {}", error);
                ctx.stop();
                return;
            }
            Ok(msg) => msg,
        };
        match websocket_message {
            ws::Message::Close(reason) => {
                log::debug!("Received close message: {:?}", reason);
                ctx.close(reason);
                ctx.stop();
            }
            ws::Message::Continuation(_) => {
                ctx.stop();
            }
            _ => (),
        }
    }
}

impl Handler<WebsocketStringMessage> for ExerciseWebsocket {
    type Result = ();

    fn handle(&mut self, msg: WebsocketStringMessage, ctx: &mut Self::Context) {
        ctx.text(msg.0);
    }
}
