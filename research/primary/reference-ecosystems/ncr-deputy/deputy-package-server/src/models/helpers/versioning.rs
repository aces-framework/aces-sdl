use crate::errors::{PackageServerError, ServerResponseError};
use crate::models::Version;
use crate::services::database::package::{GetPackageByNameAndVersion, GetVersionsByPackageName};
use crate::AppState;
use actix::{Actor, Handler};
use actix_web::{web::Data, Error, HttpResponse, Result as ActixWebResult};
use anyhow::Result;
use deputy_library::rest::VersionRest;
use log::error;

pub async fn get_package_by_name_and_version<T>(
    name: String,
    version: String,
    include_readme: bool,
    app_state: Data<AppState<T>>,
) -> ActixWebResult<Version, ServerResponseError>
where
    T: Actor + Handler<GetPackageByNameAndVersion>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetPackageByNameAndVersion>,
{
    app_state
        .database_address
        .send(GetPackageByNameAndVersion {
            name,
            version,
            include_readme,
        })
        .await
        .map_err(|error| {
            error!("Failed to get package: {error}");
            ServerResponseError(PackageServerError::MailboxError.into())
        })?
        .map_err(|error| {
            error!("Failed to get package: {error}");
            ServerResponseError(PackageServerError::DatabaseRecordNotFound.into())
        })
}

pub async fn get_packages_by_name<T>(
    name: String,
    include_readme: bool,
    app_state: Data<AppState<T>>,
) -> ActixWebResult<Vec<Version>, ServerResponseError>
where
    T: Actor + Handler<GetVersionsByPackageName>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetVersionsByPackageName>,
{
    app_state
        .database_address
        .send(GetVersionsByPackageName {
            name,
            include_readme,
        })
        .await
        .map_err(|error| {
            error!("Failed to get package: {error}");
            ServerResponseError(PackageServerError::MailboxError.into())
        })?
        .map_err(|error| {
            error!("Failed to get package: {error}");
            ServerResponseError(PackageServerError::DatabaseRecordNotFound.into())
        })
}

pub fn validate_version(
    uploadable_version: &str,
    package_versions: Vec<Version>,
) -> Result<HttpResponse, Error> {
    let rest_packages = package_versions
        .into_iter()
        .map(|package_version| package_version.into())
        .collect::<Vec<VersionRest>>();
    if let Ok(existing_option) = VersionRest::is_latest_version(uploadable_version, rest_packages) {
        if let Some(existing) = existing_option {
            error!("Package version on the server is either same or later: {existing}");
            return Err(
                ServerResponseError(PackageServerError::VersionConflict(existing).into()).into(),
            );
        }
    } else {
        error!("Failed to validate versioning");
        return Err(ServerResponseError(PackageServerError::VersionParse.into()).into());
    }
    Ok(HttpResponse::Ok().body("OK"))
}
