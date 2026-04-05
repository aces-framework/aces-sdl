use super::helpers::uuid::Uuid;
use crate::{
    constants::{MAX_EXERCISE_NAME_LENGTH, NAIVEDATETIME_DEFAULT_VALUE},
    errors::RangerError,
    middleware::keycloak::KeycloakInfo,
    schema::exercises,
    services::database::{All, Create, FilterExisting, SelectById, SoftDeleteById, UpdateById},
    utilities::Validation,
};
use anyhow::{anyhow, Result};
use chrono::NaiveDateTime;
use diesel::{
    insert_into, AsChangeset, ExpressionMethods, Insertable, QueryDsl, Queryable, Selectable,
    SelectableHelper,
};
use serde::{Deserialize, Serialize};
use std::result::Result as StdResult;

#[derive(Insertable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = exercises)]
pub struct NewExercise {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub deployment_group: String,
    pub sdl_schema: Option<String>,
    pub group_name: Option<String>,
}

impl NewExercise {
    pub fn create_insert(&self) -> Create<&Self, exercises::table> {
        insert_into(exercises::table).values(self)
    }
}

impl Validation for NewExercise {
    fn validate(&self) -> StdResult<(), RangerError> {
        if self.name.len() > MAX_EXERCISE_NAME_LENGTH {
            return Err(RangerError::ExerciseNameTooLong);
        }
        Ok(())
    }
}

#[derive(Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = exercises)]
pub struct Exercise {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub deployment_group: String,
    pub sdl_schema: Option<String>,
    pub group_name: Option<String>,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
}

impl Exercise {
    fn all_with_deleted() -> All<exercises::table, Self> {
        exercises::table.select(Self::as_select())
    }

    pub fn all() -> FilterExisting<All<exercises::table, Self>, exercises::deleted_at> {
        Self::all_with_deleted().filter(exercises::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(
        id: Uuid,
    ) -> SelectById<exercises::table, exercises::id, exercises::deleted_at, Self> {
        Self::all().filter(exercises::id.eq(id))
    }

    pub fn soft_delete(
        &self,
    ) -> SoftDeleteById<exercises::id, exercises::deleted_at, exercises::table> {
        diesel::update(exercises::table.filter(exercises::id.eq(self.id)))
            .set(exercises::deleted_at.eq(diesel::dsl::now))
    }

    pub async fn is_member(
        &self,
        user_id: String,
        keycloak_info: KeycloakInfo,
        realm_name: String,
    ) -> Result<bool> {
        let role_name = self
            .group_name
            .clone()
            .ok_or_else(|| anyhow!("Exercise group name is not set"))?;
        let users = keycloak_info
            .service_user
            .realm_clients_with_id_roles_with_role_name_users_get(
                &realm_name,
                &keycloak_info.client_id,
                &role_name,
                None,
                None,
            )
            .await?;
        for user in users {
            if let Some(loop_user_id) = user.id {
                if loop_user_id == user_id {
                    return Ok(true);
                }
            }
        }
        Ok(false)
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ParticipantExercise {
    pub id: Uuid,
    pub name: String,
    pub updated_at: String,
}

impl From<Exercise> for ParticipantExercise {
    fn from(exercise: Exercise) -> Self {
        Self {
            id: exercise.id,
            name: exercise.name,
            updated_at: exercise.updated_at.to_string(),
        }
    }
}

#[derive(AsChangeset, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = exercises)]
pub struct UpdateExercise {
    pub name: String,
    pub deployment_group: String,
    pub sdl_schema: Option<String>,
    pub group_name: Option<String>,
}

impl UpdateExercise {
    pub fn create_update(
        &self,
        id: Uuid,
    ) -> UpdateById<exercises::id, exercises::deleted_at, exercises::table, &Self> {
        diesel::update(exercises::table)
            .filter(exercises::id.eq(id))
            .filter(exercises::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
            .set(self)
    }
}
