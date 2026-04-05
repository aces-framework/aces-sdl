use actix_web::Result;
use actix_web_actors::ws;
use crate::{
    services::websocket::LogWebSocket,
    AppState,
};
use log::Level as LogLevel;
use actix_web::{
    get,
    web::{Payload, Data, Path},
    HttpRequest, HttpResponse,
};

#[get("/websocket/{level}")]
pub async fn subscribe_to_logs_with_level(
    req: HttpRequest,
    stream: Payload,
    app_state: Data<AppState>,
    path: Path<String>,
) -> Result<HttpResponse> {
    let level = match path.as_str() {
        "info" => LogLevel::Info,
        "debug" => LogLevel::Debug,
        "error" => LogLevel::Error,
        "warn" => LogLevel::Warn,
        other => {
            log::warn!("Received unrecognized log level: {}", other);
            LogLevel::Info
        }
    };

    subscribe_to_logs(req, stream, app_state, level).await
}

async fn subscribe_to_logs(
    req: HttpRequest,
    stream: Payload,
    app_state: Data<AppState>,
    log_level: LogLevel,
) -> Result<HttpResponse> {
    log::debug!("Subscribing websocket to {} logs", log_level);
    let manager_address = app_state.websocket_manager_address.clone();
    let log_socket = LogWebSocket::new(manager_address, log_level);
    log::debug!("Created websocket for {} logs", log_level);
    ws::start(log_socket, &req, stream)
}
