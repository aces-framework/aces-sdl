use crate::models::helpers::grpc_package::SerializableGrpcPackage;
use crate::models::BannerContentRest;
use crate::services::deployer::{
    DeputyPackageQueryByType, DeputyPackageQueryCheckPackageExists,
    DeputyPackageQueryGetBannerFile, DeputyPackageQueryGetExercise,
};
use crate::services::deployment::GetDefaultDeployers;
use crate::utilities::{
    create_database_error_handler, create_mailbox_error_handler, create_package_error_handler,
    get_query_param,
};
use crate::AppState;
use actix_web::web::{Data, Json, Query};
use actix_web::{get, post, Error, HttpResponse};
use anyhow::Result;
use ranger_grpc::DeputyStreamResponse;
use ranger_grpc::Source;
use sdl_parser::common::Source as SdlSource;
use std::collections::HashMap;
use tonic::Streaming;

#[get("")]
pub async fn get_deputy_packages_by_type(
    app_state: Data<AppState>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<HttpResponse, Error> {
    let deployers = app_state
        .deployment_manager_address
        .send(GetDefaultDeployers())
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get default deployers"))?;

    let package_type = get_query_param(&params, "type")?;

    let query_result = app_state
        .deployer_distributor_address
        .send(DeputyPackageQueryByType(package_type, deployers))
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get packages"))?;

    let serializable_packages: Vec<SerializableGrpcPackage> =
        query_result.into_iter().map(Into::into).collect();

    Ok(HttpResponse::Ok()
        .content_type("application/json")
        .json(serializable_packages))
}

#[get("")]
pub async fn get_exercise_by_source(
    app_state: Data<AppState>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<HttpResponse, Error> {
    let deployers = app_state
        .deployment_manager_address
        .send(GetDefaultDeployers())
        .await
        .map_err(create_mailbox_error_handler("Deputy Query"))?
        .map_err(create_database_error_handler("Get default deployers"))?;

    let source = Source {
        name: get_query_param(&params, "name")?,
        version: get_query_param(&params, "version")?,
    };

    let sdl_schema = app_state
        .deployer_distributor_address
        .send(DeputyPackageQueryGetExercise(source, deployers))
        .await
        .map_err(create_mailbox_error_handler("Deputy Query"))?
        .map_err(create_database_error_handler("Get exercise package"))?;

    Ok(HttpResponse::Ok()
        .content_type("application/json")
        .json(sdl_schema))
}

#[get("")]
pub async fn get_deputy_banner_file(
    app_state: Data<AppState>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<HttpResponse, Error> {
    let deployers = app_state
        .deployment_manager_address
        .send(GetDefaultDeployers())
        .await
        .map_err(create_mailbox_error_handler("Deputy Query"))?
        .map_err(create_database_error_handler("Get default deployers"))?;
    let name = get_query_param(&params, "name")?;
    let version = get_query_param(&params, "version")?;

    let source = Source {
        name: name.clone(),
        version,
    };

    let mut banner_file: Streaming<DeputyStreamResponse> = app_state
        .deployer_distributor_address
        .send(DeputyPackageQueryGetBannerFile(source, deployers))
        .await
        .map_err(create_mailbox_error_handler("Deputy Query"))?
        .map_err(create_database_error_handler("Get banner file"))?;

    let mut banner_buffer = Vec::new();
    while let Ok(Some(stream_response)) = banner_file.message().await {
        banner_buffer.extend_from_slice(&stream_response.chunk);
    }

    let banner_content_rest: BannerContentRest = BannerContentRest {
        name,
        content: banner_buffer,
    };

    Ok(HttpResponse::Ok()
        .content_type("application/json")
        .json(banner_content_rest))
}

#[post("")]
pub async fn check_package_exists(
    app_state: Data<AppState>,
    sources: Json<Vec<SdlSource>>,
) -> Result<HttpResponse, Error> {
    let deployers = app_state
        .deployment_manager_address
        .send(GetDefaultDeployers())
        .await
        .map_err(create_mailbox_error_handler("Deputy Query"))?
        .map_err(create_database_error_handler("Get default deployers"))?;

    let sources: Vec<SdlSource> = sources.into_inner();

    for sdl_source in sources {
        let source = Source {
            name: sdl_source.name,
            version: sdl_source.version,
        };

        app_state
            .deployer_distributor_address
            .send(DeputyPackageQueryCheckPackageExists(
                source.clone(),
                deployers.clone(),
            ))
            .await
            .map_err(create_mailbox_error_handler("Deputy Query"))?
            .map_err(create_package_error_handler(
                "Check package exists".to_string(),
                source.name,
            ))?;
    }

    Ok(HttpResponse::Ok().finish())
}
