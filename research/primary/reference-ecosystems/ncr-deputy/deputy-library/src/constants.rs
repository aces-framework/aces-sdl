use crate::project::ContentType;
use duration_str::parse;
use fancy_regex::Regex;
use lazy_static::lazy_static;
use std::time::Duration;

pub const PACKAGE_TOML: &str = "package.toml";

pub const LOCKFILE: &str = "deputy.lock";
pub const LOCKFILE_TIMEOUT: &str = "5min";
pub const LOCKFILE_SLEEP: &str = "250ms";

lazy_static! {
    pub static ref VALID_NAME: Regex =
        Regex::new(r#"^[a-zA-Z0-9](?:[a-zA-Z0-9_-]*[a-zA-Z0-9])?$"#).unwrap();
    static ref LOCKFILE_TIMEOUT_DURATION: Duration =
        parse(LOCKFILE_TIMEOUT).expect("Error parsing lockfile timeout duration");
    pub static ref LOCKFILE_SLEEP_DURATION: Duration =
        parse(LOCKFILE_SLEEP).expect("Error parsing lockfile sleep duration");
    pub static ref LOCKFILE_TRIES: u64 =
        { LOCKFILE_TIMEOUT_DURATION.as_millis() / LOCKFILE_SLEEP_DURATION.as_millis() } as u64;
}

pub const MIN_NAME_LENGTH: usize = 3;
pub const MAX_NAME_LENGTH: usize = 50;

pub const SHA256_LENGTH: usize = 64;

pub const COMPRESSION_CHUNK_SIZE: usize = 131_072;

pub const PAYLOAD_CHUNK_SIZE: u64 = 8192;

pub const fn default_max_archive_size() -> u64 {
    30 * 1024 * 1024 * 1024 // 30 GB
}

pub const CONFIGURATION_FOLDER_PATH_ENV_KEY: &str = "DEPUTY_CONFIG_FOLDER";

pub const ASSETS_REQUIRED_PACKAGE_TYPES: [ContentType; 4] = [
    ContentType::Feature,
    ContentType::Condition,
    ContentType::Inject,
    ContentType::Malware,
];
