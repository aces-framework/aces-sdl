use crate::{
    schema::{email_templates, emails},
    services::database::{All, Create, DeleteById, SelectByIdFromAll},
};
use chrono::NaiveDateTime;
use diesel::{
    helper_types::{Eq, Filter},
    insert_into, ExpressionMethods, Insertable, QueryDsl, Queryable, Selectable, SelectableHelper,
};
use lettre::{
    message::{header, SinglePart},
    Message,
};
use serde::{Deserialize, Serialize};
use std::error::Error;

use super::{helpers::uuid::Uuid, EmailStatus};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EmailResource {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub to_addresses: Vec<String>,
    pub reply_to_addresses: Option<Vec<String>>,
    pub cc_addresses: Option<Vec<String>>,
    pub bcc_addresses: Option<Vec<String>>,
    pub subject: String,
    pub body: String,
    pub user_id: Option<String>,
}

impl EmailResource {
    pub fn create_message(&self, from_address: String) -> Result<Message, Box<dyn Error>> {
        let mut message_builder = Message::builder()
            .from(from_address.parse()?)
            .subject(self.subject.clone());

        for to_address in self.to_addresses.clone() {
            if !to_address.trim().is_empty() {
                message_builder = message_builder.to(to_address.trim().parse()?);
            }
        }

        if let Some(reply_to_addresses) = &self.reply_to_addresses {
            for reply_to_address in reply_to_addresses.clone() {
                if !reply_to_address.trim().is_empty() {
                    message_builder = message_builder.reply_to(reply_to_address.trim().parse()?);
                }
            }
        }

        if let Some(cc_addresses) = &self.cc_addresses {
            for cc_address in cc_addresses.clone() {
                if !cc_address.trim().is_empty() {
                    message_builder = message_builder.cc(cc_address.trim().parse()?);
                }
            }
        }

        if let Some(bcc_addresses) = &self.bcc_addresses {
            for bcc_address in bcc_addresses.clone() {
                if !bcc_address.trim().is_empty() {
                    message_builder = message_builder.bcc(bcc_address.trim().parse()?);
                }
            }
        }

        Ok(message_builder.singlepart(
            SinglePart::builder()
                .header(header::ContentType::TEXT_HTML)
                .body(self.body.clone()),
        )?)
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, Insertable, Queryable, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = emails)]
pub struct NewEmail {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub exercise_id: Uuid,
    pub user_id: Option<String>,
    pub from_address: String,
    pub to_addresses: String,
    pub reply_to_addresses: Option<String>,
    pub cc_addresses: Option<String>,
    pub bcc_addresses: Option<String>,
    pub subject: String,
    pub body: String,
}

impl NewEmail {
    pub fn new(resource: EmailResource, from_address: String, exercise_id: Uuid) -> Self {
        Self {
            id: resource.id,
            exercise_id,
            user_id: resource.user_id,
            from_address,
            to_addresses: resource.to_addresses.join(","),
            reply_to_addresses: resource
                .reply_to_addresses
                .map(|addresses| addresses.join(",")),
            cc_addresses: resource.cc_addresses.map(|addresses| addresses.join(",")),
            bcc_addresses: resource.bcc_addresses.map(|addresses| addresses.join(",")),
            subject: resource.subject,
            body: resource.body,
        }
    }

    pub fn create_insert(&self) -> Create<&Self, emails::table> {
        insert_into(emails::table).values(self)
    }
}

#[derive(Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = emails)]
pub struct Email {
    pub id: Uuid,
    pub exercise_id: Uuid,
    pub user_id: Option<String>,
    pub from_address: String,
    pub to_addresses: String,
    pub reply_to_addresses: Option<String>,
    pub cc_addresses: Option<String>,
    pub bcc_addresses: Option<String>,
    pub subject: String,
    pub body: String,
    pub created_at: NaiveDateTime,
}

impl Email {
    pub fn all() -> All<emails::table, Self> {
        emails::table.select(Self::as_select())
    }

    pub fn by_exercise_id(
        exercise_id: Uuid,
    ) -> SelectByIdFromAll<emails::table, emails::exercise_id, Self> {
        Self::all().filter(emails::exercise_id.eq(exercise_id))
    }

    pub fn by_id(id: Uuid) -> SelectByIdFromAll<emails::table, emails::id, Self> {
        Self::all().filter(emails::id.eq(id))
    }

    pub fn hard_delete(&self) -> DeleteById<emails::id, emails::table> {
        diesel::delete(emails::table.filter(emails::id.eq(self.id)))
    }
}

#[derive(Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EmailWithStatus {
    pub id: Uuid,
    pub exercise_id: Uuid,
    pub user_id: Option<String>,
    pub from_address: String,
    pub to_addresses: String,
    pub reply_to_addresses: Option<String>,
    pub cc_addresses: Option<String>,
    pub bcc_addresses: Option<String>,
    pub subject: String,
    pub body: String,
    pub status_type: String,
    pub status_message: Option<String>,
    pub created_at: NaiveDateTime,
}

impl EmailWithStatus {
    pub fn new(email: Email, email_status: EmailStatus) -> Self {
        Self {
            id: email.id,
            exercise_id: email.exercise_id,
            user_id: email.user_id,
            from_address: email.from_address,
            to_addresses: email.to_addresses,
            reply_to_addresses: email.reply_to_addresses,
            cc_addresses: email.cc_addresses,
            bcc_addresses: email.bcc_addresses,
            subject: email.subject,
            body: email.body,
            status_type: email_status.name.to_string(),
            status_message: email_status.message,
            created_at: email.created_at,
        }
    }
}

#[derive(Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[diesel(table_name = email_templates)]
pub struct EmailTemplate {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub content: String,
    pub created_at: NaiveDateTime,
}

impl EmailTemplate {
    pub fn all() -> All<email_templates::table, Self> {
        email_templates::table.select(Self::as_select())
    }

    pub fn by_id(
        id: Uuid,
    ) -> Filter<All<email_templates::table, Self>, Eq<email_templates::id, Uuid>> {
        Self::all().filter(email_templates::id.eq(id))
    }

    pub fn hard_delete(&self) -> DeleteById<email_templates::id, email_templates::table> {
        diesel::delete(email_templates::table.filter(email_templates::id.eq(self.id)))
    }
}

#[derive(Insertable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[diesel(table_name = email_templates)]
pub struct NewEmailTemplate {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub content: String,
}

impl NewEmailTemplate {
    pub fn create_insert(&self) -> Create<&Self, email_templates::table> {
        insert_into(email_templates::table).values(self)
    }
}
