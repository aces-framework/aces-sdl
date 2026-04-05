use crate::middleware::authentication::local_token::UserTokenInfo;
use crate::models::helpers::versioning::{
    get_package_by_name_and_version, get_packages_by_name, validate_version,
};
use crate::services::database::package::{
    CreateCategory, CreatePackage, GetAllCategories, GetPackageByNameAndVersion, GetPackages,
    GetVersionsByPackageName, UpdateVersionMsg,
};
use crate::{
    constants::{default_limit, default_page, default_pagination},
    errors::{PackageServerError, ServerResponseError},
    models::Category,
    AppState,
};
use actix::{Actor, Handler};
use actix_files::NamedFile;
use actix_http::error::PayloadError;
use actix_web::{
    web::{Bytes, Data, Json, Path, Payload, Query},
    Error, HttpResponse,
};
use anyhow::Result;
use async_stream::try_stream;
use deputy_library::constants::PACKAGE_TOML;
use deputy_library::rest::PackagesWithVersionsAndPagesRest;
use deputy_library::validation::{Validate, ValidatePackage};
use deputy_library::{
    archiver::ArchiveStreamer,
    package::{Package, PackageFile, PackageMetadata},
    rest::VersionRest,
    validation::{validate_name, validate_version_semantic},
};
use futures::{Stream, StreamExt};
use log::{debug, error, info};
use semver::{Version, VersionReq};
use serde::Deserialize;
use serde_with::{formats::CommaSeparator, StringWithSeparator};
use std::path::PathBuf;
use urlencoding::encode;

async fn drain_stream(
    stream: impl Stream<Item = Result<Bytes, PayloadError>> + Unpin + 'static,
) -> Result<(), Error> {
    stream
        .filter_map(|x| async move { x.ok().map(Ok) })
        .forward(futures::sink::drain())
        .await?;
    Ok(())
}

pub async fn add_package<T>(
    body: Payload,
    app_state: Data<AppState<T>>,
    user_info: UserTokenInfo,
) -> Result<HttpResponse, Error>
where
    T: Actor
        + Handler<CreatePackage>
        + Handler<GetVersionsByPackageName>
        + Handler<GetPackageByNameAndVersion>
        + Handler<GetPackages>
        + Handler<CreateCategory>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, CreatePackage>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetVersionsByPackageName>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetPackageByNameAndVersion>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetPackages>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, CreateCategory>,
{
    let (mut package_metadata, body) =
        PackageMetadata::from_stream(body).await.map_err(|error| {
            error!("Failed to parse package metadata: {error}");
            ServerResponseError(PackageServerError::MetadataParse.into())
        })?;

    package_metadata.validate().map_err(|error| {
        error!("Failed to validate the package metadata: {error}");
        ServerResponseError(PackageServerError::MetadataValidation.into())
    })?;

    let versions: Vec<crate::models::Version> =
        get_packages_by_name(package_metadata.clone().name, false, app_state.clone()).await?;
    if let Err(error) = validate_version(package_metadata.version.as_str(), versions) {
        drain_stream(body).await?;
        return Err(error);
    }

    let archive_file: PackageFile = PackageFile::from_stream(body).await.map_err(|error| {
        error!("Failed to save the file: {error}");
        ServerResponseError(PackageServerError::FileSave.into())
    })?;

    let mut package = Package::new(package_metadata.clone(), archive_file);

    package
        .validate(app_state.max_archive_size)
        .map_err(|error| {
            error!(
                "Package \"{name}\" did not pass validation: {error}",
                name = package_metadata.name
            );
            ServerResponseError(PackageServerError::PackageValidation.into())
        })?;

    package.save(&app_state.package_folder).map_err(|error| {
        error!("Failed to save the package: {error}");
        ServerResponseError(PackageServerError::PackageSave.into())
    })?;

    let package_metadata = package.metadata.clone();
    let readme_html = package_metadata
        .readme_html(app_state.package_folder.clone().into())
        .await
        .map_err(|error| {
            error!("Failed to generate the readme html: {error}");
            ServerResponseError(PackageServerError::ReadmeParse.into())
        })?
        .unwrap_or_default();
    let response = app_state
        .database_address
        .send(CreatePackage(
            (package_metadata, readme_html).into(),
            user_info.email.clone(),
        ))
        .await
        .map_err(|error| {
            error!("Failed to add package: {error}");
            ServerResponseError(PackageServerError::PackageSave.into())
        })?
        .map_err(|error| {
            error!("Failed to add package: {error}");
            ServerResponseError(PackageServerError::PackageSave.into())
        })?;
    let optional_categories = package.metadata.categories;
    if let Some(categories) = optional_categories {
        for category in categories {
            app_state
                .database_address
                .send(CreateCategory(category.into(), response.0.id))
                .await
                .map_err(|error| {
                    error!("Failed to add category: {error}");
                    ServerResponseError(PackageServerError::PackageSave.into())
                })?
                .map_err(|error| {
                    error!("Failed to add category: {error}");
                    ServerResponseError(PackageServerError::PackageSave.into())
                })?;
        }
    }
    Ok(HttpResponse::Ok().body("OK"))
}

pub async fn download_package<T>(
    path_variables: Path<(String, String)>,
    app_state: Data<AppState<T>>,
) -> Result<NamedFile, Error>
where
    T: Actor + Handler<GetPackageByNameAndVersion>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetPackageByNameAndVersion>,
{
    let package_name = &path_variables.0;
    let package_version = &path_variables.1;

    validate_name(package_name.to_string()).map_err(|error| {
        error!("Failed to validate the package name: {error}");
        ServerResponseError(PackageServerError::PackageNameValidation.into())
    })?;
    validate_version_semantic(package_version.to_string()).map_err(|error| {
        error!("Failed to validate the package version: {error}");
        ServerResponseError(PackageServerError::PackageVersionValidation.into())
    })?;

    let package_path = PathBuf::from(app_state.package_folder.clone())
        .join(Package::normalize_file_path(package_name, package_version));

    let package = get_package_by_name_and_version(
        package_name.to_string(),
        package_version.to_string(),
        false,
        app_state,
    )
    .await?;

    if package.is_yanked {
        info!("Requested package \"{package_name}\" has been yanked");
        return Err(ServerResponseError(PackageServerError::PackageYanked.into()).into());
    }

    NamedFile::open(package_path).map_err(|error| {
        error!("Failed to open the package: {error}");
        Error::from(error)
    })
}

#[serde_with::serde_as]
#[serde_with::skip_serializing_none]
#[derive(Deserialize, Debug, Default)]
pub struct SearchQuery {
    #[serde(default = "default_pagination")]
    paginated: bool,
    #[serde(default = "default_page")]
    page: u32,
    #[serde(default = "default_limit")]
    limit: u32,
    #[serde(default)]
    search_term: Option<String>,
    #[serde(rename = "type", default)]
    type_param: Option<String>,
    #[serde_as(as = "Option<StringWithSeparator::<CommaSeparator, String>>")]
    #[serde(rename = "categories", default)]
    category_param: Option<Vec<String>>,
    #[serde(default)]
    include_readme: bool,
}

pub async fn get_all_packages<T>(
    app_state: Data<AppState<T>>,
    query: Query<SearchQuery>,
) -> Result<Json<PackagesWithVersionsAndPagesRest>, Error>
where
    T: Actor + Handler<GetPackages>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetPackages>,
{
    let search_term = &query.search_term;
    let optional_package_type = &query.type_param;
    let optional_package_categories = &query.category_param;
    let packages_with_versions_and_pages = app_state
        .database_address
        .send(GetPackages {
            search_term: search_term.clone(),
            package_type: optional_package_type.clone(),
            categories: optional_package_categories.clone(),
            paginated: query.paginated,
            page: query.page as i64,
            per_page: query.limit as i64,
            include_readme: query.include_readme,
        })
        .await
        .map_err(|error| {
            error!("Failed to get packages by name: {error}");
            ServerResponseError(PackageServerError::Pagination.into())
        })?
        .map_err(|error| {
            error!("Failed to get packages by name: {error}");
            ServerResponseError(PackageServerError::Pagination.into())
        })?;

    Ok(Json(packages_with_versions_and_pages.into()))
}

#[derive(Deserialize, Debug, Default)]
pub struct VersionQuery {
    pub version_requirement: Option<String>,
    #[serde(default)]
    pub include_readme: bool,
}

pub async fn get_all_versions<T>(
    path_variable: Path<String>,
    app_state: Data<AppState<T>>,
    query: Query<VersionQuery>,
) -> Result<Json<Vec<VersionRest>>, Error>
where
    T: Actor + Handler<GetVersionsByPackageName>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetVersionsByPackageName>,
{
    let package_name = path_variable.into_inner();
    validate_name(package_name.to_string()).map_err(|error| {
        error!("Failed to validate the package name: {error}");
        ServerResponseError(PackageServerError::PackageNameValidation.into())
    })?;
    let version_requirement = match &query.version_requirement {
        Some(version_requirement) => match VersionReq::parse(version_requirement) {
            Ok(version_requirement) => Some(version_requirement),
            Err(error) => {
                error!("Failed to validate the version requirement: {error}");
                return Err(ServerResponseError(
                    PackageServerError::PackageVersionRequirementValidation.into(),
                )
                .into());
            }
        },
        None => None,
    };

    let packages: Vec<VersionRest> =
        get_packages_by_name(package_name.to_string(), query.include_readme, app_state)
            .await?
            .into_iter()
            .filter_map(|package| match &version_requirement {
                Some(version_requirement) => {
                    if let Ok(version) = Version::parse(&package.version) {
                        if version_requirement.matches(&version) && !package.is_yanked {
                            return Some(package);
                        }
                    }
                    None
                }
                None => Some(package),
            })
            .map(|package| package.into())
            .collect();
    Ok(Json(packages))
}

pub async fn download_file<T>(
    path_variables: Path<(String, String, String)>,
    app_state: Data<AppState<T>>,
) -> Result<HttpResponse, Error>
where
    T: Actor + Handler<GetPackageByNameAndVersion>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetPackageByNameAndVersion>,
{
    let package_name = &path_variables.clone().0;
    let package_version = &path_variables.1;
    let file_path_in_package = path_variables.clone().2;

    let package_path = PathBuf::from(&app_state.package_folder)
        .join(Package::normalize_file_path(package_name, package_version));

    let package = get_package_by_name_and_version(
        package_name.to_string(),
        package_version.to_string(),
        false,
        app_state,
    )
    .await?;

    if package.is_yanked && file_path_in_package != PACKAGE_TOML {
        info!("Package \"{package_name}\" has been yanked, requested file {file_path_in_package} can not be served");
        return Err(ServerResponseError(PackageServerError::PackageYanked.into()).into());
    }

    let file_pathbuf = PathBuf::from(&file_path_in_package);
    let stream = try_stream! {
        let mut archive = ArchiveStreamer::prepare_archive(package_path).map_err(|error| {
            error!("Failed to open the package: {error}");
            ServerResponseError(PackageServerError::FileNotFound.into())
        })?;
        let mut archive_stream = ArchiveStreamer::try_new(&mut archive, file_pathbuf)
            .map_err(|error| {
                error!("Failed to open the package: {error}");
                ServerResponseError(PackageServerError::FileNotFound.into())
            })?
            .ok_or_else(|| {
                error!("File not found from the archive");
                ServerResponseError(PackageServerError::FileNotFound.into())
            })?;

        while let Some(row) = archive_stream.next().await {
            yield row?;
        }
    };
    let _: &dyn Stream<Item = Result<_, Error>> = &stream;

    let filename_pathbuf = PathBuf::from(&file_path_in_package);
    let filename = filename_pathbuf.file_name().and_then(|name| name.to_str());
    let filename = match filename {
        Some(name) => name,
        None => {
            error!("Filename is missing in the file path: {file_path_in_package}");
            return Ok(HttpResponse::InternalServerError().finish());
        }
    };

    Ok(HttpResponse::Ok()
        .insert_header((
            actix_http::header::CONTENT_DISPOSITION,
            format!(
                "attachment; filename=\"{}\"; filename*=UTF-8''{}",
                filename,
                encode(filename)
            ),
        ))
        .insert_header((
            actix_http::header::CONTENT_TYPE,
            mime_guess::from_path(filename).first_or_octet_stream(),
        ))
        .streaming(Box::pin(stream)))
}

#[derive(Deserialize, Debug, Default)]
pub struct ReadmeQuery {
    #[serde(default)]
    pub include_readme: bool,
}

pub async fn get_package_version<T>(
    path_variables: Path<(String, String)>,
    app_state: Data<AppState<T>>,
    query: Query<ReadmeQuery>,
) -> Result<Json<VersionRest>, Error>
where
    T: Actor + Handler<GetPackageByNameAndVersion>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetPackageByNameAndVersion>,
{
    let package_name = &path_variables.0;
    let package_version = &path_variables.1;

    let package_version = get_package_by_name_and_version(
        package_name.to_string(),
        package_version.to_string(),
        query.include_readme,
        app_state,
    )
    .await?;

    Ok(Json(package_version.into()))
}

pub async fn yank_version<T>(
    path_variables: Path<(String, String, String)>,
    app_state: Data<AppState<T>>,
    user_info: UserTokenInfo,
) -> Result<Json<crate::models::Version>, Error>
where
    T: Actor + Handler<UpdateVersionMsg> + Handler<GetPackageByNameAndVersion>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, UpdateVersionMsg>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetPackageByNameAndVersion>,
{
    let package_name = &path_variables.0;
    let package_version = &path_variables.1;
    let set_yank = &path_variables.2;

    let mut package_version = get_package_by_name_and_version(
        package_name.to_string(),
        package_version.to_string(),
        true,
        app_state.clone(),
    )
    .await?;
    package_version.is_yanked = match set_yank.as_str() {
        "false" => false,
        "true" => true,
        _ => true,
    };
    let response = app_state
        .database_address
        .send(UpdateVersionMsg {
            id: package_version.id,
            version: package_version,
        })
        .await
        .map_err(|error| {
            error!("Failed to update version: {error}");
            ServerResponseError(PackageServerError::VersionUpdate.into())
        })?
        .map_err(|error| {
            error!("Failed to update version: {error}");
            ServerResponseError(PackageServerError::VersionUpdate.into())
        })?;
    debug!(
        "Package {package_name} was yanked by {owner_email}",
        owner_email = user_info.email
    );
    Ok(Json(response))
}

pub async fn get_all_categories<T>(
    app_state: Data<AppState<T>>,
) -> Result<Json<Vec<Category>>, Error>
where
    T: Actor + Handler<GetAllCategories>,
    <T as Actor>::Context: actix::dev::ToEnvelope<T, GetAllCategories>,
{
    let categories: Vec<Category> = app_state
        .database_address
        .send(GetAllCategories)
        .await
        .map_err(|error| {
            error!("Failed to get categories: {error}");
            ServerResponseError(PackageServerError::MailboxError.into())
        })?
        .map_err(|error| {
            error!("Failed to get categories: {error}");
            ServerResponseError(PackageServerError::DatabaseRecordNotFound.into())
        })?;
    Ok(Json(categories))
}
