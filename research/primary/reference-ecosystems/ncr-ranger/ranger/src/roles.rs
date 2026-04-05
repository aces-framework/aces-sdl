use std::fmt::{Display, Formatter, Result};

use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq, Hash)]
pub enum RangerRole {
    Admin,
    Participant,
    Client,
}

impl Display for RangerRole {
    fn fmt(&self, f: &mut Formatter) -> Result {
        match self {
            RangerRole::Admin => write!(f, "ranger-manager"),
            RangerRole::Participant => write!(f, "ranger-participant"),
            RangerRole::Client => write!(f, "ranger-client"),
        }
    }
}
