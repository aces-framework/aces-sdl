use super::helpers::uuid::Uuid;
use crate::{
    constants::NAIVEDATETIME_DEFAULT_VALUE,
    schema::accounts,
    services::database::{
        All, Create, FilterExisting, SelectById, SelectByTemplateId, SelectByTemplateIdAndUsername,
        SoftDeleteById, UpdateById,
    },
};
use chrono::NaiveDateTime;
use diesel::{
    insert_into, AsChangeset, ExpressionMethods, Insertable, QueryDsl, Queryable, Selectable,
    SelectableHelper,
};
use serde::{Deserialize, Serialize};

#[derive(Insertable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = accounts)]
pub struct NewAccount {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub template_id: Uuid,
    pub username: String,
    pub password: Option<String>,
    pub private_key: Option<String>,
    pub exercise_id: Uuid,
}

impl NewAccount {
    pub fn create_insert(&self) -> Create<&Self, accounts::table> {
        insert_into(accounts::table).values(self)
    }
}

#[derive(Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = accounts)]
pub struct Account {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub template_id: Uuid,
    pub username: String,
    pub password: Option<String>,
    pub private_key: Option<String>,
    pub exercise_id: Uuid,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub deleted_at: NaiveDateTime,
}

impl Account {
    fn all_with_deleted() -> All<accounts::table, Self> {
        accounts::table.select(Self::as_select())
    }

    pub fn all() -> FilterExisting<All<accounts::table, Self>, accounts::deleted_at> {
        Self::all_with_deleted().filter(accounts::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(
        id: Uuid,
    ) -> SelectById<accounts::table, accounts::id, accounts::deleted_at, Self> {
        Self::all().filter(accounts::id.eq(id))
    }

    pub fn by_template_id(
        template_id: Uuid,
    ) -> SelectByTemplateId<accounts::table, accounts::template_id, accounts::deleted_at, Self>
    {
        Self::all().filter(accounts::template_id.eq(template_id))
    }

    pub fn by_template_id_and_username(
        template_id: Uuid,
        username: String,
    ) -> SelectByTemplateIdAndUsername<
        accounts::table,
        accounts::template_id,
        accounts::username,
        accounts::deleted_at,
        Self,
    > {
        Self::all()
            .filter(accounts::template_id.eq(template_id))
            .filter(accounts::username.eq(username))
    }

    pub fn soft_delete(
        &self,
    ) -> SoftDeleteById<accounts::id, accounts::deleted_at, accounts::table> {
        diesel::update(accounts::table.filter(accounts::id.eq(self.id)))
            .set(accounts::deleted_at.eq(diesel::dsl::now))
    }
}

#[derive(AsChangeset, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = accounts)]
pub struct UpdateAccount {
    pub username: String,
    pub password: Option<String>,
    pub private_key: Option<String>,
}

impl UpdateAccount {
    pub fn create_update(
        &self,
        id: Uuid,
    ) -> UpdateById<accounts::id, accounts::deleted_at, accounts::table, &Self> {
        diesel::update(accounts::table)
            .filter(accounts::id.eq(id))
            .filter(accounts::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
            .set(self)
    }
}
