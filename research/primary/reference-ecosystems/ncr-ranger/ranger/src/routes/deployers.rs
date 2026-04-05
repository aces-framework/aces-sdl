use crate::AppState;
use actix_web::web::Data;
use actix_web::{get, Error, HttpResponse};
use anyhow::Result;

#[get("")]
pub async fn get_deployers(app_state: Data<AppState>) -> Result<HttpResponse, Error> {
    let deployment_groups = app_state.configuration.deployment_groups.clone();

    Ok(HttpResponse::Ok()
        .content_type("application/json")
        .json(deployment_groups))
}

#[get("default")]
pub async fn default_deployer(app_state: Data<AppState>) -> Result<HttpResponse, Error> {
    let default_deployer_group = app_state.configuration.default_deployment_group.clone();

    Ok(HttpResponse::Ok()
        .content_type("application/json")
        .json(default_deployer_group))
}
