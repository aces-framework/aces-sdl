pub mod deployment;
pub mod event_info;
pub mod events;
pub mod metric;
pub mod participants;
pub mod scenario;
pub mod score;

use crate::{
    errors::RangerError,
    middleware::{authentication::UserInfo, exercise::ExerciseInfo, keycloak::KeycloakInfo},
    models::{Exercise, ParticipantExercise},
    services::database::exercise::GetExercises,
    utilities::{create_database_error_handler, create_mailbox_error_handler},
    AppState,
};
use actix_web::{
    get,
    web::{Data, Json},
};
use futures_util::future::join_all;

#[get("")]
pub async fn get_participant_exercises(
    app_state: Data<AppState>,
    user_info: UserInfo,
    keycloak_info: KeycloakInfo,
) -> Result<Json<Vec<ParticipantExercise>>, RangerError> {
    let exercises = app_state
        .database_address
        .send(GetExercises)
        .await
        .map_err(create_mailbox_error_handler("Database"))?
        .map_err(create_database_error_handler("Get exercises"))?;

    let exercise_with_members: Vec<(Exercise, bool)> =
        join_all(exercises.into_iter().map(|exercise| async {
            let is_member = exercise
                .is_member(
                    user_info.id.clone(),
                    KeycloakInfo(keycloak_info.clone()),
                    app_state.configuration.keycloak.realm.clone(),
                )
                .await
                .unwrap_or(false);
            (exercise, is_member)
        }))
        .await;
    let exercises = exercise_with_members
        .into_iter()
        .filter_map(|(exercise, is_member)| {
            if is_member {
                return Some(exercise);
            }
            None
        })
        .collect::<Vec<_>>();

    let participant_exercises = exercises
        .into_iter()
        .map(ParticipantExercise::from)
        .collect();

    Ok(Json(participant_exercises))
}

#[get("")]
pub async fn get_participant_exercise(
    exercise: ExerciseInfo,
) -> Result<Json<ParticipantExercise>, RangerError> {
    let exercise = exercise.into_inner().into();

    Ok(Json(exercise))
}
