use actix_http::{body::BoxBody, StatusCode};
use actix_web::{error::ResponseError, HttpResponse};
use log::error;
use thiserror::Error as ThisError;

#[derive(ThisError, Debug)]
pub enum RangerError {
    #[error("This scenario doesn't exist")]
    ScenarioNotFound,
    #[error("Internal server error")]
    ActixMailBoxError,
    #[error("Failed to deploy scenario")]
    DeploymentFailed,
    #[error("Failed to undeploy exercise")]
    UndeploymentFailed,
    #[error("DeployerGroup not found")]
    DeployerGroupNotfound,
    #[error("Exercise name too long")]
    ExerciseNameTooLong,
    #[error("Exercise not found")]
    ExericseNotFound,
    #[error("Deployment not found")]
    DeploymentNotFound,
    #[error("Deployment name too long")]
    DeploymentNameTooLong,
    #[error("Order name too long")]
    OrderNameTooLong,
    #[error("Order not found")]
    OrderNotFound,
    #[error("Custom element not found")]
    CustomElementNotFound,
    #[error("Failed to parse uuid")]
    UuidParsingFailed,
    #[error("Failed to parse scenario")]
    ScenarioParsingFailed,
    #[error("Internal server error")]
    DatabaseUnexpected,
    #[error("Entity not found")]
    EntityNotFound,
    #[error("Metric not found")]
    MetricNotFound,
    #[error("Conflict")]
    DatabaseConflict,
    #[error("Not found")]
    DatabaseRecordNotFound,
    #[error("Mailer configuration not found")]
    MailerConfigurationNotFound,
    #[error("Failed to create email message")]
    EmailMessageCreationFailed,
    #[error("Failed to send email")]
    EmailSendingFailed,
    #[error("Keycloak query failed")]
    KeycloakQueryFailed,
    #[error("User info missing")]
    UserInfoMissing,
    #[error("Application cannot access necessary configuration")]
    ConfigurationMissing,
    #[error("Access forbidden for this path")]
    AccessForbidden,
    #[error("Token expired")]
    TokenExpired,
    #[error("Token missing")]
    TokenMissing,
    #[error("App state missing")]
    AppStateMissing,
    #[error("Not authorized")]
    NotAuthorized,
    #[error("Failed to upload the file")]
    FileUploadFailed,
    #[error("Failed to read the file")]
    FileReadFailed,
    #[error("File not found")]
    FileNotFound,
    #[error("Failed to delete the file")]
    FileDeletionFailed,
    #[error("Metric has already been scored")]
    MetricAlreadyScored,
    #[error("Payload too large")]
    PayloadTooLarge,
    #[error("Unsupported media type")]
    UnsupportedMediaType,
    #[error("Missing query parameter \"{0}\"")]
    MissingParameter(String),
    #[error("Failed to create Websocket connection")]
    WebsocketFailed,
    #[error("Failed to find package: {0}")]
    PackageCheckFailed(String),
    #[error("Deputy server error")]
    DeputyQueryFailed,
}

impl ResponseError for RangerError {
    fn status_code(&self) -> StatusCode {
        match self {
            RangerError::ScenarioNotFound => StatusCode::NOT_FOUND,
            RangerError::DeployerGroupNotfound => StatusCode::NOT_FOUND,
            RangerError::CustomElementNotFound => StatusCode::NOT_FOUND,
            RangerError::ExerciseNameTooLong => StatusCode::UNPROCESSABLE_ENTITY,
            RangerError::OrderNameTooLong => StatusCode::UNPROCESSABLE_ENTITY,
            RangerError::OrderNotFound => StatusCode::NOT_FOUND,
            RangerError::ExericseNotFound => StatusCode::NOT_FOUND,
            RangerError::DeploymentNotFound => StatusCode::NOT_FOUND,
            RangerError::DeploymentNameTooLong => StatusCode::UNPROCESSABLE_ENTITY,
            RangerError::UuidParsingFailed => StatusCode::UNPROCESSABLE_ENTITY,
            RangerError::ScenarioParsingFailed => StatusCode::UNPROCESSABLE_ENTITY,
            RangerError::DatabaseConflict => StatusCode::CONFLICT,
            RangerError::EntityNotFound => StatusCode::NOT_FOUND,
            RangerError::MetricNotFound => StatusCode::NOT_FOUND,
            RangerError::DatabaseRecordNotFound => StatusCode::NOT_FOUND,
            RangerError::MailerConfigurationNotFound => StatusCode::NOT_FOUND,
            RangerError::AccessForbidden => StatusCode::FORBIDDEN,
            RangerError::TokenExpired => StatusCode::UNAUTHORIZED,
            RangerError::TokenMissing => StatusCode::UNAUTHORIZED,
            RangerError::NotAuthorized => StatusCode::UNAUTHORIZED,
            RangerError::MetricAlreadyScored => StatusCode::FORBIDDEN,
            RangerError::PayloadTooLarge => StatusCode::PAYLOAD_TOO_LARGE,
            RangerError::UnsupportedMediaType => StatusCode::UNSUPPORTED_MEDIA_TYPE,
            RangerError::MissingParameter(_) => StatusCode::BAD_REQUEST,
            RangerError::PackageCheckFailed(_) => StatusCode::NOT_FOUND,
            RangerError::FileNotFound => StatusCode::NOT_FOUND,
            _ => StatusCode::INTERNAL_SERVER_ERROR,
        }
    }

    fn error_response(&self) -> HttpResponse<BoxBody> {
        error!("Error: {:?}", self);
        HttpResponse::with_body(self.status_code(), format!("{self}")).map_into_boxed_body()
    }
}
