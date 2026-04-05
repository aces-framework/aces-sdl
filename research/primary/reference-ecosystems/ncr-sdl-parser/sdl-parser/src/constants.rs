use lazy_static::lazy_static;
use regex::Regex;

pub const MINIMUM_NODE_COUNT: i32 = 1;
pub const DEFAULT_NODE_COUNT: i32 = 1;
pub const fn default_node_count() -> i32 {
    DEFAULT_NODE_COUNT
}

pub const MAX_LONG_NAME: usize = 35;

lazy_static! {
    pub static ref CWE_REGEX: Regex = Regex::new(r"CWE-\d+").unwrap();
}

pub const DEFAULT_SPEED_VALUE: f64 = 1.0;
pub const fn default_speed_value() -> f64 {
    DEFAULT_SPEED_VALUE
}
