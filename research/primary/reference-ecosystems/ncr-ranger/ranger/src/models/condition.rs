use super::helpers::uuid::Uuid;
use crate::{
    constants::NAIVEDATETIME_DEFAULT_VALUE,
    schema::condition_messages,
    services::database::{All, Create, FilterExisting, SelectById, SoftDeleteById},
};
use bigdecimal::BigDecimal;
use chrono::NaiveDateTime;
use diesel::{
    helper_types::{Eq, Filter},
    insert_into, ExpressionMethods, Insertable, QueryDsl, Queryable, Selectable, SelectableHelper,
};
use serde::{Deserialize, Serialize};

#[derive(Insertable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = condition_messages)]
pub struct NewConditionMessage {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub exercise_id: Uuid,
    pub deployment_id: Uuid,
    pub virtual_machine_id: Uuid,
    pub condition_name: String,
    pub condition_id: Uuid,
    pub value: BigDecimal,
}

impl NewConditionMessage {
    pub fn new(
        exercise_id: Uuid,
        deployment_id: Uuid,
        virtual_machine_id: Uuid,
        condition_name: String,
        condition_id: Uuid,
        value: BigDecimal,
    ) -> Self {
        Self {
            id: Uuid::random(),
            exercise_id,
            deployment_id,
            virtual_machine_id,
            condition_name,
            condition_id,
            value,
        }
    }

    pub fn create_insert(&self) -> Create<&Self, condition_messages::table> {
        insert_into(condition_messages::table).values(self)
    }
}

#[derive(Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = condition_messages)]
pub struct ConditionMessage {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub exercise_id: Uuid,
    pub deployment_id: Uuid,
    pub virtual_machine_id: Uuid,
    pub condition_name: String,
    pub condition_id: Uuid,
    pub value: BigDecimal,
    pub created_at: NaiveDateTime,
    pub deleted_at: NaiveDateTime,
}

pub type ConditonMessages = Vec<ConditionMessage>;

type ByExerciseId<T> = Filter<
    FilterExisting<T, condition_messages::deleted_at>,
    Eq<condition_messages::exercise_id, Uuid>,
>;

type ByDeploymentId<T> = Filter<
    FilterExisting<T, condition_messages::deleted_at>,
    Eq<condition_messages::deployment_id, Uuid>,
>;

impl ConditionMessage {
    fn all_with_deleted() -> All<condition_messages::table, Self> {
        condition_messages::table.select(Self::as_select())
    }

    pub fn all(
    ) -> FilterExisting<All<condition_messages::table, Self>, condition_messages::deleted_at> {
        Self::all_with_deleted()
            .filter(condition_messages::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(
        id: Uuid,
    ) -> SelectById<
        condition_messages::table,
        condition_messages::id,
        condition_messages::deleted_at,
        Self,
    > {
        Self::all().filter(condition_messages::id.eq(id))
    }

    pub fn by_deployment_id(
        deployment_id: Uuid,
    ) -> ByDeploymentId<All<condition_messages::table, Self>> {
        Self::all().filter(condition_messages::deployment_id.eq(deployment_id))
    }

    pub fn by_exercise_id(exercise_id: Uuid) -> ByExerciseId<All<condition_messages::table, Self>> {
        Self::all().filter(condition_messages::exercise_id.eq(exercise_id))
    }

    pub fn soft_delete(
        &self,
    ) -> SoftDeleteById<
        condition_messages::id,
        condition_messages::deleted_at,
        condition_messages::table,
    > {
        diesel::update(condition_messages::table.filter(condition_messages::id.eq(self.id)))
            .set(condition_messages::deleted_at.eq(diesel::dsl::now))
    }
}
