use actix::{Actor, Addr};

pub mod configuration;
pub mod constants;
mod errors;
pub mod middleware;
pub mod models;
pub mod routes;
pub mod schema;
pub mod services;
#[cfg(feature = "test")]
pub mod test;
pub mod utilities;

#[derive(Clone, Debug)]
pub struct AppState<T>
where
    T: Actor,
{
    pub database_address: Addr<T>,
    pub package_folder: String,
    pub max_archive_size: u64,
}
