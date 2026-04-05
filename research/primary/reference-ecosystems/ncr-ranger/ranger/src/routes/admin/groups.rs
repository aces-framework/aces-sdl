use crate::{errors::RangerError, middleware::keycloak::KeycloakInfo, AppState};
use actix_web::{
    get,
    web::{Data, Json, Path},
};
use keycloak::types::{RoleRepresentation, UserRepresentation};
use log::error;

#[get("")]
pub async fn get_participant_groups(
    app_state: Data<AppState>,
    keycloak_info: KeycloakInfo,
) -> Result<Json<Vec<RoleRepresentation>>, RangerError> {
    let roles = keycloak_info
        .service_user
        .realm_clients_with_id_roles_get(
            &app_state.configuration.keycloak.realm,
            &keycloak_info.client_id,
            None,
            None,
            None,
            None,
        )
        .await
        .map_err(|error| {
            error!("Failed to get keycloak clients: {error}");
            RangerError::KeycloakQueryFailed
        })?;

    Ok(Json(roles))
}

#[get("/{group_name}/users")]
pub async fn get_participant_groups_users(
    path_variables: Path<String>,
    app_state: Data<AppState>,
    keycloak_info: KeycloakInfo,
) -> Result<Json<Vec<UserRepresentation>>, RangerError> {
    let role_name = path_variables.into_inner();
    let users = keycloak_info
        .service_user
        .realm_clients_with_id_roles_with_role_name_users_get(
            &app_state.configuration.keycloak.realm,
            &keycloak_info.client_id,
            &role_name,
            None,
            None,
        )
        .await
        .map_err(|error| {
            error!("Failed to get keycloak clients: {error}");
            RangerError::KeycloakQueryFailed
        })?;

    Ok(Json(users))
}
