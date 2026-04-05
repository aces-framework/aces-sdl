use crate::{errors::RangerError, middleware::deployment::DeploymentInfo};
use actix_web::{get, web::Json};
use anyhow::Result;
use log::error;
use sdl_parser::{parse_sdl, Scenario};

#[get("scenario")]
pub async fn get_admin_exercise_deployment_scenario(
    deployment: DeploymentInfo,
) -> Result<Json<Scenario>, RangerError> {
    let scenario = parse_sdl(&deployment.sdl_schema).map_err(|error| {
        error!("Failed to parse sdl: {error}");
        RangerError::ScenarioParsingFailed
    })?;

    Ok(Json(scenario))
}
