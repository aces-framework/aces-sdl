use chrono::NaiveDateTime;
use diesel::{
    deserialize::FromSqlRow,
    expression::AsExpression,
    helper_types::{Desc, Limit, Order},
    insert_into,
    prelude::QueryableByName,
    sql_types::Text,
    ExpressionMethods, Insertable, QueryDsl, Queryable, Selectable, SelectableHelper,
};
use serde::{Deserialize, Serialize};

use crate::{
    schema::email_statuses,
    services::database::{All, Create, SelectByEmailId, SelectByIdFromAll},
};

use super::helpers::uuid::Uuid;

#[derive(Clone, Debug, PartialEq, FromSqlRow, AsExpression, Eq, Deserialize, Serialize)]
#[diesel(sql_type = Text)]
pub enum EmailStatusName {
    Pending,
    Sent,
    Failed,
}

#[derive(Clone, Debug, Deserialize, Serialize, Insertable)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = email_statuses)]
pub struct NewEmailStatus {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub email_id: Uuid,
    pub name: EmailStatusName,
    pub message: Option<String>,
}

impl NewEmailStatus {
    pub fn new(email_id: Uuid, name: EmailStatusName, message: Option<String>) -> Self {
        Self {
            id: Uuid::random(),
            email_id,
            name,
            message,
        }
    }

    pub fn new_pending(email_id: Uuid) -> Self {
        Self::new(email_id, EmailStatusName::Pending, None)
    }

    pub fn new_sent(email_id: Uuid, message: Option<&str>) -> Self {
        Self::new(
            email_id,
            EmailStatusName::Sent,
            message.map(|s| s.to_string()),
        )
    }

    pub fn new_failed(email_id: Uuid, message: String) -> Self {
        Self::new(email_id, EmailStatusName::Failed, Some(message))
    }

    pub fn create_insert(&self) -> Create<&Self, email_statuses::table> {
        insert_into(email_statuses::table).values(self)
    }
}

#[derive(
    Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize, QueryableByName,
)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = email_statuses)]
pub struct EmailStatus {
    pub id: Uuid,
    pub email_id: Uuid,
    pub name: EmailStatusName,
    pub message: Option<String>,
    pub created_at: NaiveDateTime,
}

impl EmailStatus {
    pub fn all() -> All<email_statuses::table, Self> {
        email_statuses::table.select(Self::as_select())
    }

    pub fn by_id(id: Uuid) -> SelectByIdFromAll<email_statuses::table, email_statuses::id, Self> {
        Self::all().filter(email_statuses::id.eq(id))
    }

    pub fn by_email_id(
        email_id: Uuid,
    ) -> SelectByEmailId<email_statuses::table, email_statuses::email_id, Self> {
        Self::all().filter(email_statuses::email_id.eq(email_id))
    }

    pub fn by_email_id_latest(
        email_id: Uuid,
    ) -> Limit<
        Order<
            SelectByEmailId<email_statuses::table, email_statuses::email_id, Self>,
            Desc<email_statuses::created_at>,
        >,
    > {
        Self::by_email_id(email_id)
            .order(email_statuses::created_at.desc())
            .limit(1)
    }
}
