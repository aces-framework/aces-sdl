use super::helpers::uuid::Uuid;
use crate::{
    constants::NAIVEDATETIME_DEFAULT_VALUE,
    schema::participants::{self},
    services::database::{
        All, Create, FilterExisting, SelectByDeploymentId, SelectById, SoftDeleteById,
    },
};
use chrono::NaiveDateTime;
use diesel::{
    insert_into, ExpressionMethods, Insertable, QueryDsl, Queryable, Selectable, SelectableHelper,
};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NewParticipantResource {
    pub user_id: String,
    pub selector: String,
}

#[derive(Insertable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = participants)]
pub struct NewParticipant {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub deployment_id: Uuid,
    pub user_id: String,
    pub selector: String,
}

impl NewParticipant {
    pub fn create_insert(&self) -> Create<&Self, participants::table> {
        insert_into(participants::table).values(self)
    }
}

#[derive(Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = participants)]
pub struct Participant {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub deployment_id: Uuid,
    pub user_id: String,
    pub selector: String,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub deleted_at: NaiveDateTime,
}

impl Participant {
    fn all_with_deleted() -> All<participants::table, Self> {
        participants::table.select(Self::as_select())
    }

    pub fn all() -> FilterExisting<All<participants::table, Self>, participants::deleted_at> {
        Self::all_with_deleted().filter(participants::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(
        id: Uuid,
    ) -> SelectById<participants::table, participants::id, participants::deleted_at, Self> {
        Self::all().filter(participants::id.eq(id))
    }

    pub fn by_deployment_id(
        deployment_uuid: Uuid,
    ) -> SelectByDeploymentId<
        participants::table,
        participants::deployment_id,
        participants::deleted_at,
        Self,
    > {
        Self::all().filter(participants::deployment_id.eq(deployment_uuid))
    }

    pub fn soft_delete(
        &self,
    ) -> SoftDeleteById<participants::id, participants::deleted_at, participants::table> {
        diesel::update(participants::table.filter(participants::id.eq(self.id)))
            .set(participants::deleted_at.eq(diesel::dsl::now))
    }
}
