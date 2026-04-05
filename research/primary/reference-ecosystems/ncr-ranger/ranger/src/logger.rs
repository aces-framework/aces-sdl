use crate::constants::{DEFAULT_LOGGER_ENV_KEY, DEFAULT_LOGGER_LEVEL, PROJECT_NAME};
use crate::services::websocket::{SocketLogUpdate, WebSocketManager, WebsocketStringMessage};
use actix::Addr;
use log::{Level, LevelFilter, Log, Metadata, Record};
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::sync::Mutex;

pub struct FileWriterLogger {
    file: Mutex<File>,
}

impl FileWriterLogger {
    pub fn new(log_file: &str) -> Result<Self, std::io::Error> {
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(log_file)?;

        Ok(FileWriterLogger {
            file: Mutex::new(file),
        })
    }

    fn log_to_file(&self, level: Level, args: &std::fmt::Arguments) {
        if let Ok(mut file) = self.file.lock() {
            let now = chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ");
            if let Err(e) = writeln!(file, "{} [{}] {}", now, level, args) {
                eprintln!("Failed to write to log file: {}", e);
            }
        }
    }
}

impl Log for FileWriterLogger {
    fn enabled(&self, _: &Metadata) -> bool {
        true
    }

    fn log(&self, record: &Record) {
        self.log_to_file(record.level(), &format_args!("{}", record.args()));
    }

    fn flush(&self) {
        if let Ok(mut file) = self.file.lock() {
            if let Err(e) = file.flush() {
                eprintln!("Failed to flush log file: {}", e);
            }
        }
    }
}

pub struct WebsocketLogger {
    websocket_manager: Addr<WebSocketManager>,
}

impl WebsocketLogger {
    pub fn new(websocket_manager: Addr<WebSocketManager>) -> Self {
        WebsocketLogger { websocket_manager }
    }
}

impl Log for WebsocketLogger {
    fn enabled(&self, _: &Metadata) -> bool {
        true
    }

    fn log(&self, record: &Record) {
        if record
            .module_path()
            .is_some_and(|module| module.contains(PROJECT_NAME))
        {
            let message = format!(
                "{} [{}] {}",
                chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ"),
                record.level(),
                record.args()
            );
            let _ = self.websocket_manager.try_send(SocketLogUpdate(
                WebsocketStringMessage(message),
                record.level(),
            ));
        }
    }

    fn flush(&self) {}
}

pub struct CombinedLogger {
    console_logger: env_logger::Logger,
    file_logger: FileWriterLogger,
    websocket_logger: WebsocketLogger,
}

impl CombinedLogger {
    pub fn new(
        file_path: &str,
        websocket_manager: Addr<WebSocketManager>,
    ) -> Result<Self, std::io::Error> {
        let file_logger = FileWriterLogger::new(file_path)?;

        let mut builder = env_logger::Builder::from_env(DEFAULT_LOGGER_ENV_KEY);
        builder.format(|buf, record| {
            writeln!(
                buf,
                "{} [{}] {} - {}",
                chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ"),
                record.level(),
                record.target(),
                record.args()
            )
        });
        let environment_log_level = std::env::var(DEFAULT_LOGGER_ENV_KEY)
            .unwrap_or_else(|_| DEFAULT_LOGGER_LEVEL.to_string());
        let level_filter: LevelFilter = environment_log_level.parse().unwrap_or(LevelFilter::Info);

        builder.filter(None, LevelFilter::Info);
        builder.filter_module(PROJECT_NAME, level_filter);
        let console_logger = builder.build();

        let websocket_logger = WebsocketLogger::new(websocket_manager);

        Ok(Self {
            console_logger,
            file_logger,
            websocket_logger,
        })
    }
}

impl Log for CombinedLogger {
    fn enabled(&self, metadata: &Metadata) -> bool {
        self.console_logger.enabled(metadata)
            || self.file_logger.enabled(metadata)
            || self.websocket_logger.enabled(metadata)
    }

    fn log(&self, record: &Record) {
        if self.console_logger.enabled(record.metadata()) {
            self.console_logger.log(record);
        }
        if self.file_logger.enabled(record.metadata()) {
            self.file_logger.log(record);
        }
        if self.websocket_logger.enabled(record.metadata()) {
            self.websocket_logger.log(record);
        }
    }

    fn flush(&self) {
        self.console_logger.flush();
        self.file_logger.flush();
        self.websocket_logger.flush();
    }
}

pub fn init(
    log_file: &str,
    websocket_manager: Addr<WebSocketManager>,
) -> Result<(), Box<dyn std::error::Error>> {
    let logger = CombinedLogger::new(log_file, websocket_manager)?;
    log::set_boxed_logger(Box::new(logger))?;
    log::set_max_level(LevelFilter::Trace);

    Ok(())
}
