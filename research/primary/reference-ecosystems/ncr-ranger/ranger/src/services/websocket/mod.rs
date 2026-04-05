mod exercise;
mod logger;

use crate::models::{
    helpers::{uuid::Uuid, websocket_wrapper::WebsocketWrapper},
    Deployment, DeploymentElement, Event, Score, UpdateExercise,
};
use actix::{Actor, Context, Handler, Message, Recipient};
use anyhow::{anyhow, Result};
pub use exercise::ExerciseWebsocket;
use log::Level as LogLevel;
pub use logger::LogWebSocket;
use std::collections::{HashMap, HashSet};

#[derive(Default)]
pub struct WebSocketManager {
    pub exercise_websockets: HashMap<Uuid, HashMap<Uuid, Recipient<WebsocketStringMessage>>>,
    pub log_websockets: HashMap<LogLevel, HashSet<Recipient<WebsocketStringMessage>>>,
}

impl WebSocketManager {
    pub fn new() -> Self {
        Self {
            exercise_websockets: HashMap::new(),
            log_websockets: HashMap::new(),
        }
    }

    fn get_exercise_targets(&self, exercise_uuid: Uuid) -> Vec<Recipient<WebsocketStringMessage>> {
        if let Some(update_targets) = self.exercise_websockets.get(&exercise_uuid) {
            let update_targets = update_targets.values().cloned().collect::<Vec<_>>();
            return update_targets;
        }

        vec![]
    }
}

impl Actor for WebSocketManager {
    type Context = Context<Self>;
}

#[derive(Message, Clone)]
#[rtype(result = "()")]
pub struct WebsocketStringMessage(pub String);

#[derive(Message, Debug)]
#[rtype(result = "Result<()>")]
pub struct RegisterExerciseSocket(Uuid, Uuid, Recipient<WebsocketStringMessage>);

impl Handler<RegisterExerciseSocket> for WebSocketManager {
    type Result = Result<()>;

    fn handle(&mut self, msg: RegisterExerciseSocket, _: &mut Context<Self>) -> Self::Result {
        let RegisterExerciseSocket(exercise_id, recipient_id, recipient) = msg;

        self.exercise_websockets
            .entry(exercise_id)
            .and_modify(|exercise_websockets| {
                exercise_websockets.insert(recipient_id, recipient.clone());
            })
            .or_insert_with(move || {
                let mut new_map = HashMap::new();
                new_map.insert(recipient_id, recipient);
                new_map
            });
        Ok(())
    }
}

#[derive(Message, Debug)]
#[rtype(result = "Result<()>")]
pub struct RegisterLogSocket {
    pub recipient: Recipient<WebsocketStringMessage>,
    pub log_level: LogLevel,
}

impl Handler<RegisterLogSocket> for WebSocketManager {
    type Result = Result<(), anyhow::Error>;

    fn handle(&mut self, msg: RegisterLogSocket, _: &mut Context<Self>) -> Self::Result {
        self.log_websockets
            .entry(msg.log_level)
            .or_default()
            .insert(msg.recipient);
        Ok(())
    }
}
#[derive(Message, Debug)]
#[rtype(result = "Result<()>")]
pub struct UnRegisterExercise(Uuid, Uuid);

impl Handler<UnRegisterExercise> for WebSocketManager {
    type Result = Result<()>;

    fn handle(&mut self, msg: UnRegisterExercise, _: &mut Context<Self>) -> Self::Result {
        let UnRegisterExercise(exercise_id, recipient_id) = msg;

        let exercise_websockets = self
            .exercise_websockets
            .get_mut(&exercise_id)
            .ok_or_else(|| anyhow!("No exercise websockets found for exercise: {}", exercise_id))?;

        exercise_websockets
            .remove(&recipient_id)
            .ok_or_else(|| anyhow!("No recipient found for id: {}", recipient_id))?;

        Ok(())
    }
}

#[derive(Message, Debug)]
#[rtype(result = "Result<()>")]
pub struct UnRegisterLogSocket(Recipient<WebsocketStringMessage>);

impl Handler<UnRegisterLogSocket> for WebSocketManager {
    type Result = Result<(), anyhow::Error>;

    fn handle(&mut self, msg: UnRegisterLogSocket, _: &mut Context<Self>) -> Self::Result {
        self.log_websockets.values_mut().for_each(|recipients| {
            recipients.remove(&msg.0);
        });
        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct SocketExerciseUpdate(pub Uuid, pub WebsocketWrapper<UpdateExercise>);

impl Handler<SocketExerciseUpdate> for WebSocketManager {
    type Result = Result<()>;

    fn handle(&mut self, msg: SocketExerciseUpdate, _: &mut Context<Self>) -> Self::Result {
        let SocketExerciseUpdate(exercise_uuid, update_message) = msg;
        let targets = self.get_exercise_targets(exercise_uuid);
        for target in targets {
            target.do_send(WebsocketStringMessage(serde_json::to_string(
                &update_message,
            )?));
        }

        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct SocketLogUpdate(pub WebsocketStringMessage, pub LogLevel);

impl Handler<SocketLogUpdate> for WebSocketManager {
    type Result = Result<(), anyhow::Error>;

    fn handle(&mut self, msg: SocketLogUpdate, _: &mut Context<Self>) -> Self::Result {
        for (level, targets) in &self.log_websockets {
            if *level >= msg.1 {
                for target in targets.iter() {
                    target
                        .try_send(msg.0.clone())
                        .map_err(|e| anyhow!("Failed to send log update: {}", e))?;
                }
            }
        }

        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct SocketDeployment(pub Uuid, pub WebsocketWrapper<Deployment>);

impl Handler<SocketDeployment> for WebSocketManager {
    type Result = Result<()>;

    fn handle(&mut self, msg: SocketDeployment, _: &mut Context<Self>) -> Self::Result {
        let SocketDeployment(exercise_uuid, deployment) = msg;
        let targets = self.get_exercise_targets(exercise_uuid);
        for target in targets {
            target.do_send(WebsocketStringMessage(serde_json::to_string(&deployment)?));
        }

        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct SocketDeploymentElement(pub Uuid, pub WebsocketWrapper<DeploymentElement>);

impl Handler<SocketDeploymentElement> for WebSocketManager {
    type Result = Result<()>;

    fn handle(&mut self, msg: SocketDeploymentElement, _: &mut Context<Self>) -> Self::Result {
        let SocketDeploymentElement(exercise_uuid, deployment_element) = msg;
        let targets = self.get_exercise_targets(exercise_uuid);
        for target in targets {
            target.do_send(WebsocketStringMessage(serde_json::to_string(
                &deployment_element,
            )?));
        }

        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct SocketScoring(pub Uuid, pub WebsocketWrapper<Score>);

impl Handler<SocketScoring> for WebSocketManager {
    type Result = Result<()>;

    fn handle(&mut self, msg: SocketScoring, _: &mut Context<Self>) -> Self::Result {
        let SocketScoring(exercise_uuid, score) = msg;
        let targets = self.get_exercise_targets(exercise_uuid);
        for target in targets {
            target.do_send(WebsocketStringMessage(serde_json::to_string(&score)?));
        }

        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct SocketEvent(pub Uuid, pub WebsocketWrapper<Event>);

impl Handler<SocketEvent> for WebSocketManager {
    type Result = Result<()>;

    fn handle(&mut self, msg: SocketEvent, _: &mut Context<Self>) -> Self::Result {
        let SocketEvent(exercise_uuid, event) = msg;
        let targets = self.get_exercise_targets(exercise_uuid);
        for target in targets {
            target.do_send(WebsocketStringMessage(serde_json::to_string(&event)?));
        }

        Ok(())
    }
}
