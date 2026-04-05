use super::helpers::uuid::Uuid;
use crate::{
    schema::banners,
    services::database::{All, Create, HardUpdateById},
};
use chrono::NaiveDateTime;
use diesel::{
    helper_types::{Eq, Filter},
    insert_into,
    query_builder::{DeleteStatement, IntoUpdateTarget},
    AsChangeset, ExpressionMethods, Insertable, QueryDsl, Queryable, Selectable, SelectableHelper,
};
use serde::{Deserialize, Serialize};

#[derive(Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = banners)]
pub struct Banner {
    pub exercise_id: Uuid,
    pub name: String,
    pub content: Vec<u8>,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
}

impl Banner {
    pub fn all() -> All<banners::table, Self> {
        banners::table.select(Self::as_select())
    }

    pub fn by_id(id: Uuid) -> Filter<All<banners::table, Self>, Eq<banners::exercise_id, Uuid>> {
        Self::all().filter(banners::exercise_id.eq(id))
    }

    pub fn hard_delete(
        &self,
    ) -> Filter<
        DeleteStatement<banners::table, <banners::table as IntoUpdateTarget>::WhereClause>,
        Eq<banners::exercise_id, Uuid>,
    > {
        diesel::delete(banners::table).filter(banners::exercise_id.eq(self.exercise_id))
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
pub struct NewBanner {
    pub name: String,
    pub content: Vec<u8>,
}

#[derive(Insertable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = banners)]
pub struct NewBannerWithId {
    pub exercise_id: Uuid,
    pub name: String,
    pub content: Vec<u8>,
}

impl NewBannerWithId {
    pub fn create_insert(&self) -> Create<&Self, banners::table> {
        insert_into(banners::table).values(self)
    }
}

#[derive(AsChangeset, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = banners)]
pub struct UpdateBanner {
    pub name: String,
    pub content: Vec<u8>,
}

impl UpdateBanner {
    pub fn create_update(
        &self,
        id: Uuid,
    ) -> HardUpdateById<banners::exercise_id, banners::table, &Self> {
        diesel::update(banners::table)
            .filter(banners::exercise_id.eq(id))
            .set(self)
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
pub struct BannerContentRest {
    pub name: String,
    pub content: Vec<u8>,
}
