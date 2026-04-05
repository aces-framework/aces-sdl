use super::{RegisterLogSocket, UnRegisterLogSocket, WebSocketManager, WebsocketStringMessage};
use log::Level as LogLevel;
use actix::{Actor, ActorContext, Addr, AsyncContext, Handler, Running, StreamHandler};
use actix_web_actors::ws;

pub struct LogWebSocket {
    manager_address: Addr<WebSocketManager>,
    log_level: LogLevel,
}

impl LogWebSocket {
    pub fn new(manager_address: Addr<WebSocketManager>, log_level: LogLevel) -> Self {
        Self {
            manager_address,
            log_level,
        }
    }
}

impl Actor for LogWebSocket {
    type Context = ws::WebsocketContext<Self>;

    fn started(&mut self, ctx: &mut Self::Context) {
        let recipient = ctx.address().recipient();
        self.manager_address.do_send(RegisterLogSocket {
            recipient,
            log_level: self.log_level,
        });
    }

    fn stopping(&mut self, ctx: &mut Self::Context) -> Running {
        let recipient = ctx.address().recipient();
        self.manager_address.do_send(UnRegisterLogSocket(recipient));
        Running::Stop
    }
}

impl StreamHandler<Result<ws::Message, ws::ProtocolError>> for LogWebSocket {
    fn handle(&mut self, msg: Result<ws::Message, ws::ProtocolError>, ctx: &mut Self::Context) {
        match msg {
            Ok(ws::Message::Close(reason)) => {
                ctx.close(reason);
                ctx.stop();
            }
            Err(error) => {
                log::error!("Failed to receive websocket message: {}", error);
                ctx.stop();
            }
            _ => (),
        }
    }
}

impl Handler<WebsocketStringMessage> for LogWebSocket {
    type Result = ();

    fn handle(&mut self, msg: WebsocketStringMessage, ctx: &mut Self::Context) {
        ctx.text(msg.0);
    }
}
