use bigdecimal::{BigDecimal, FromPrimitive};
use chrono::NaiveDateTime;
use lazy_static::lazy_static;
use std::{collections::HashMap, time::Duration};

pub const PROJECT_NAME: &str = env!("CARGO_PKG_NAME");
const DEFAULT_DEPLOYER_GROUP_NAME: &str = "default";
pub const DEFAULT_LOGGER_ENV_KEY: &str = "RUST_LOG";
pub const DEFAULT_LOGGER_LEVEL: &str = "INFO";

pub const fn default_deployment_group_name() -> &'static str {
    DEFAULT_DEPLOYER_GROUP_NAME
}

pub const MAX_DEPLOYMENT_NAME_LENGTH: usize = 20;
pub const MAX_EXERCISE_NAME_LENGTH: usize = 20;
pub const MAX_ORDER_NAME_LENGTH: usize = 20;
pub const MAX_ARTIFACT_FILE_SIZE: usize = 10_000_000;

pub const RECORD_NOT_FOUND: &str = "Record not found";
pub const DUPLICATE_ENTRY: &str = "Duplicate entry";
pub const FOREIGN_KEY_CONSTRAINT_FAILS: &str = "a foreign key constraint fails";
pub const PACKAGE_CHECK_FAILED: &str = "Failed to get package checksum";

pub const NAIVEDATETIME_DEFAULT_STRING: &str = "1970-01-01 00:00:01";
pub const DATETIME_FORMAT: &str = "%Y-%m-%d %H:%M:%S";

pub const EVENT_POLLER_RETRY_DURATION: Duration = Duration::from_secs(3);

pub const OCTET_STREAM_MIME_TYPE: &str = "application/octet-stream";

lazy_static! {
    pub static ref NAIVEDATETIME_DEFAULT_VALUE: NaiveDateTime =
        NaiveDateTime::parse_from_str(NAIVEDATETIME_DEFAULT_STRING, DATETIME_FORMAT).unwrap();
    pub static ref BIG_DECIMAL_ONE: BigDecimal = BigDecimal::from_i8(1).unwrap();
    pub static ref BIG_DECIMAL_ZERO: BigDecimal = BigDecimal::from_i8(0).unwrap();
    pub static ref ARTIFACT_EXTENSION_MIME_TYPE_WHITELIST: HashMap<&'static str, &'static str> =
        vec![("zip", "application/zip")].into_iter().collect();
}
