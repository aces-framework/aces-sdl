use crate::{
    schema::event_info_data,
    services::database::{All, Create, CreateOrIgnore},
};
use chrono::NaiveDateTime;
use diesel::{
    helper_types::{Eq, Filter},
    insert_into,
    prelude::QueryableByName,
    query_builder::{DeleteStatement, IntoUpdateTarget},
    ExpressionMethods, Insertable, QueryDsl, Queryable, Selectable, SelectableHelper,
};
use serde::{Deserialize, Serialize};

#[derive(Insertable, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = event_info_data)]
pub struct NewEventInfo {
    pub checksum: String,
    pub name: String,
    pub file_name: String,
    pub file_size: u64,
    pub content: Vec<u8>,
}

impl NewEventInfo {
    pub fn create_insert(&self) -> Create<&Self, event_info_data::table> {
        insert_into(event_info_data::table).values(self)
    }

    pub fn create_insert_or_ignore(&self) -> CreateOrIgnore<&Self, event_info_data::table> {
        diesel::insert_or_ignore_into(event_info_data::table).values(self)
    }
}

#[derive(
    Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize, QueryableByName,
)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = event_info_data)]
pub struct EventInfo {
    pub checksum: String,
    pub name: String,
    pub file_name: String,
    pub file_size: u64,
    pub content: Vec<u8>,
    pub created_at: NaiveDateTime,
}
type ByChecksum<Checksum, R> = Filter<R, Eq<Checksum, String>>;
type SelectByChecksumFromAll<Table, Checksum, T> = ByChecksum<Checksum, All<Table, T>>;

impl EventInfo {
    fn all() -> All<event_info_data::table, Self> {
        event_info_data::table.select(Self::as_select())
    }

    pub fn by_checksum(
        checksum: String,
    ) -> SelectByChecksumFromAll<event_info_data::table, event_info_data::checksum, Self> {
        Self::all().filter(event_info_data::checksum.eq(checksum))
    }

    pub fn hard_delete(
        &self,
    ) -> Filter<
        DeleteStatement<
            event_info_data::table,
            <event_info_data::table as IntoUpdateTarget>::WhereClause,
        >,
        Eq<event_info_data::checksum, String>,
    > {
        diesel::delete(event_info_data::table)
            .filter(event_info_data::checksum.eq(self.checksum.clone()))
    }
}

#[derive(Debug, QueryableByName, Deserialize)]
pub struct ExistsCheckResult {
    #[diesel(sql_type = diesel::sql_types::Bool)]
    pub exists: bool,
}
