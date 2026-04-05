use anyhow::Result;

pub trait Connection<T> {
    fn validate_connections(&self, potential_connections: &Option<Vec<String>>) -> Result<()>;
}
