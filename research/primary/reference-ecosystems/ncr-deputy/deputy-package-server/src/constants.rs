use chrono::NaiveDateTime;
use lazy_static::lazy_static;
use regex::Regex;

pub const fn default_pagination() -> bool {
    true
}

pub const fn default_page() -> u32 {
    1
}

pub const fn default_limit() -> u32 {
    20
}

pub const NAIVEDATETIME_DEFAULT_STRING: &str = "1970-01-01 00:00:01";
pub const DATETIME_FORMAT: &str = "%Y-%m-%d %H:%M:%S";

lazy_static! {
    pub static ref NAIVEDATETIME_DEFAULT_VALUE: NaiveDateTime =
        NaiveDateTime::parse_from_str(NAIVEDATETIME_DEFAULT_STRING, DATETIME_FORMAT).unwrap();
    pub static ref TOKEN_NAME_REGEX: Regex =
        Regex::new(r#"^[a-zA-Z0-9](?:[a-zA-Z0-9 _-]*[a-zA-Z0-9])?$"#).unwrap();
}

pub const JWT_AUDIENCE: &str = "account";

pub const MAX_TOKEN_NAME_LENGTH: usize = 255;
pub const MAX_TOKEN_EMAIL_LENGTH: usize = 255;
