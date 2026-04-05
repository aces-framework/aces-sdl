pub mod event;
pub mod scenario;
mod validation;

use crate::{
    constants::{
        DUPLICATE_ENTRY, FOREIGN_KEY_CONSTRAINT_FAILS, PACKAGE_CHECK_FAILED, RECORD_NOT_FOUND,
    },
    errors::RangerError,
};
use actix::MailboxError;
use anyhow::{anyhow, Result};
use diesel::mysql::Mysql;
use diesel_migrations::{embed_migrations, EmbeddedMigrations, MigrationHarness};
use log::error;
pub use validation::*;
pub const MIGRATIONS: EmbeddedMigrations = embed_migrations!();
use std::{collections::HashMap, path::Path, io::Write};
use actix_multipart::Multipart;
use actix_web::web;
use futures::{StreamExt, TryStreamExt};

pub fn create_mailbox_error_handler(actor_name: &str) -> impl Fn(MailboxError) -> RangerError + '_ {
    move |err| {
        error!("{} actor mailbox error: {}", actor_name, err);
        RangerError::ActixMailBoxError
    }
}

pub fn create_database_error_handler(
    action_name: &str,
) -> impl Fn(anyhow::Error) -> RangerError + '_ {
    move |err| {
        error!("{} error: {}", action_name, err);
        let error_string = format!("{err}");
        if error_string.contains(FOREIGN_KEY_CONSTRAINT_FAILS) {
            return RangerError::DatabaseConflict;
        } else if error_string.contains(RECORD_NOT_FOUND) {
            return RangerError::DatabaseRecordNotFound;
        } else if error_string.contains(DUPLICATE_ENTRY) {
            return RangerError::DatabaseConflict;
        }
        RangerError::DatabaseUnexpected
    }
}

pub fn create_package_error_handler(
    action_name: String,
    package_name: String,
) -> impl Fn(anyhow::Error) -> RangerError {
    move |err| {
        error!(
            "{} error for package '{}': {}",
            action_name, package_name, err
        );
        let error_string = format!("{err}");
        if error_string.contains(PACKAGE_CHECK_FAILED) {
            return RangerError::PackageCheckFailed(package_name.clone());
        }
        RangerError::DeputyQueryFailed
    }
}

pub fn run_migrations(
    connection: &mut impl MigrationHarness<Mysql>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync + 'static>> {
    connection.run_pending_migrations(MIGRATIONS)?;

    Ok(())
}

pub fn try_some<T>(item: Option<T>, error_message: &str) -> Result<T> {
    item.ok_or_else(|| anyhow!("{:?}", error_message))
}

pub fn get_file_extension(filename: &str) -> Option<&str> {
    let path = Path::new(filename);
    path.extension().and_then(|extension| extension.to_str())
}

pub fn get_query_param(
    query_params: &HashMap<String, String>,
    param: &str,
) -> Result<String, RangerError> {
    query_params
        .get(param)
        .cloned()
        .ok_or(RangerError::MissingParameter(param.to_string()))
}

pub async fn save_file(mut payload: Multipart, file_path: &Path) -> Result<()> {
    if let Some(folder_path) = file_path.parent() {
        std::fs::create_dir_all(folder_path)?;
    }

    while let Ok(Some(mut field)) = payload.try_next().await {
        let file_path = file_path.to_path_buf();
        let mut file_handler = web::block(|| std::fs::File::create(file_path)).await??;

        while let Some(chunk) = field.next().await {
            match chunk {
                Ok(data) => {
                    file_handler =
                        web::block(move || file_handler.write_all(&data).map(|_| file_handler))
                            .await??;
                }
                Err(error) => {
                    return Err(anyhow!("Failed to read file: {:?}", error));
                }
            }
        }
    }

    Ok(())
}
