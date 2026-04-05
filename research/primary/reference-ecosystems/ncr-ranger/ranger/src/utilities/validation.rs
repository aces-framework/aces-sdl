use crate::errors::RangerError;

pub trait Validation {
    fn validate(&self) -> Result<(), RangerError>;
}
