use super::helpers::uuid::Uuid;
use crate::{
    constants::NAIVEDATETIME_DEFAULT_VALUE,
    schema::events,
    services::database::{
        event::CreateEvent, All, Create, CreateOrIgnore, FilterExisting, SelectById,
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
#[diesel(table_name = events)]
pub struct NewEvent {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub deployment_id: Uuid,
    pub description: Option<String>,
    pub start: NaiveDateTime,
    pub end: NaiveDateTime,
}

impl NewEvent {
    pub fn create_insert(&self) -> Create<&Self, events::table> {
        insert_into(events::table).values(self)
    }

    pub fn create_insert_or_ignore(&self) -> CreateOrIgnore<&Self, events::table> {
        diesel::insert_or_ignore_into(events::table).values(self)
    }
}

impl From<CreateEvent> for NewEvent {
    fn from(event: CreateEvent) -> Self {
        Self {
            id: event.id,
            name: event.name,
            deployment_id: event.deployment_id,
            description: event.description,
            start: event.start,
            end: event.end,
        }
    }
}

#[derive(Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = events)]
pub struct Event {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub deployment_id: Uuid,
    pub start: NaiveDateTime,
    pub end: NaiveDateTime,
    pub description: Option<String>,
    pub has_triggered: bool,
    pub triggered_at: NaiveDateTime,
    pub event_info_data_checksum: Option<String>,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub deleted_at: NaiveDateTime,
}

pub type Events = Vec<Event>;

impl Event {
    fn all_with_deleted() -> All<events::table, Self> {
        events::table.select(Self::as_select())
    }

    pub fn all() -> FilterExisting<All<events::table, Self>, events::deleted_at> {
        Self::all_with_deleted().filter(events::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(id: Uuid) -> SelectById<events::table, events::id, events::deleted_at, Self> {
        Self::all().filter(events::id.eq(id))
    }

    pub fn by_deployment_id(
        deployment_id: Uuid,
    ) -> SelectById<events::table, events::deployment_id, events::deleted_at, Self> {
        Self::all().filter(events::deployment_id.eq(deployment_id))
    }

    pub fn soft_delete(&self) -> SoftDeleteById<events::id, events::deleted_at, events::table> {
        diesel::update(events::table.filter(events::id.eq(self.id)))
            .set(events::deleted_at.eq(diesel::dsl::now))
    }
}

#[derive(AsChangeset, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = events)]
pub struct UpdateEvent {
    pub has_triggered: bool,
    pub triggered_at: NaiveDateTime,
}

impl UpdateEvent {
    pub fn create_update(
        &self,
        id: Uuid,
    ) -> UpdateById<events::id, events::deleted_at, events::table, &Self> {
        diesel::update(events::table)
            .filter(events::id.eq(id))
            .filter(events::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
            .set(self)
    }
}

#[derive(AsChangeset, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = events)]
pub struct UpdateEventChecksum {
    pub event_info_data_checksum: Option<String>,
}

impl UpdateEventChecksum {
    pub fn create_update(
        &self,
        id: Uuid,
    ) -> UpdateById<events::id, events::deleted_at, events::table, &Self> {
        diesel::update(events::table)
            .filter(events::id.eq(id))
            .filter(events::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
            .set(self)
    }
}
