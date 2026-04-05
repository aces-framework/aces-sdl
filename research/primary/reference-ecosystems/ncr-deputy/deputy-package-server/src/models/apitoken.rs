use crate::{
    constants::{self, MAX_TOKEN_EMAIL_LENGTH, MAX_TOKEN_NAME_LENGTH, NAIVEDATETIME_DEFAULT_VALUE},
    models::helpers::uuid::Uuid,
    schema::tokens::{self},
    services::database::{All, Create, FilterExistingNotNull, SoftDeleteById},
};
use anyhow::{anyhow, Result};
use base64::{engine::general_purpose, Engine as _};
use chrono::NaiveDateTime;
use diesel::{helper_types::FindBy, insert_into, prelude::*};
use rand::Rng;
use serde::{Deserialize, Serialize};

#[derive(Queryable, Selectable, Eq, PartialEq, Deserialize, Serialize, Clone, Debug)]
#[diesel(table_name = tokens)]
pub struct ApiToken {
    pub id: Uuid,
    pub name: String,
    pub email: String,
    pub token: String,
    pub user_id: String,
    pub created_at: NaiveDateTime,
    pub deleted_at: NaiveDateTime,
}

impl ApiToken {
    fn all_with_deleted() -> All<tokens::table, Self> {
        tokens::table.select(Self::as_select())
    }

    pub fn all() -> FilterExistingNotNull<All<tokens::table, Self>, tokens::deleted_at> {
        Self::all_with_deleted().filter(tokens::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(
        id: Uuid,
    ) -> FindBy<FilterExistingNotNull<All<tokens::table, Self>, tokens::deleted_at>, tokens::id, Uuid>
    {
        Self::all().filter(tokens::id.eq(id))
    }

    pub fn by_token(
        token: String,
    ) -> FindBy<
        FilterExistingNotNull<All<tokens::table, Self>, tokens::deleted_at>,
        tokens::token,
        String,
    > {
        Self::all().filter(tokens::token.eq(token))
    }

    pub fn by_user_id(
        user_id: String,
    ) -> FindBy<
        FilterExistingNotNull<All<tokens::table, Self>, tokens::deleted_at>,
        tokens::user_id,
        String,
    > {
        Self::all().filter(tokens::user_id.eq(user_id))
    }

    pub fn soft_delete(&self) -> SoftDeleteById<tokens::id, tokens::deleted_at, tokens::table> {
        diesel::update(tokens::table.filter(tokens::id.eq(self.id)))
            .set(tokens::deleted_at.eq(diesel::dsl::now))
    }
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ApiTokenRest {
    pub id: Uuid,
    pub name: String,
    pub created_at: NaiveDateTime,
}

impl From<ApiToken> for ApiTokenRest {
    fn from(api_token: ApiToken) -> Self {
        Self {
            id: api_token.id,
            name: api_token.name,
            created_at: api_token.created_at,
        }
    }
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FullApiTokenRest {
    pub id: Uuid,
    pub name: String,
    pub email: String,
    pub token: String,
    pub user_id: String,
    pub created_at: NaiveDateTime,
    pub deleted_at: NaiveDateTime,
}

impl From<ApiToken> for FullApiTokenRest {
    fn from(api_token: ApiToken) -> Self {
        Self {
            id: api_token.id,
            name: api_token.name,
            email: api_token.email,
            token: api_token.token,
            user_id: api_token.user_id,
            created_at: api_token.created_at,
            deleted_at: api_token.deleted_at,
        }
    }
}

#[derive(Insertable, Deserialize, Serialize)]
#[diesel(table_name = tokens)]
#[serde(rename_all = "camelCase")]
pub struct NewApiToken {
    pub id: Uuid,
    pub name: String,
    pub email: String,
    pub token: String,
    pub user_id: String,
}

impl NewApiToken {
    pub fn create_insert(&self) -> Create<&Self, tokens::table> {
        insert_into(tokens::table).values(self)
    }
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NewApiTokenRest {
    pub name: String,
    pub email: String,
}

impl NewApiTokenRest {
    fn generate_token() -> String {
        let token_byte_length = 128;
        let random_bytes = rand::thread_rng()
            .sample_iter(&rand::distributions::Alphanumeric)
            .take(token_byte_length)
            .collect::<Vec<u8>>();
        general_purpose::STANDARD.encode(random_bytes)
    }

    pub fn validate(&self) -> Result<()> {
        if !constants::TOKEN_NAME_REGEX.is_match(&self.name) {
            return Err(anyhow!("Name contains invalid characters:".to_string()));
        }

        if self.name.len() > MAX_TOKEN_NAME_LENGTH {
            return Err(anyhow!("Token name is too long".to_string()));
        }
        if self.email.len() > MAX_TOKEN_EMAIL_LENGTH {
            return Err(anyhow!("Token email is too long".to_string()));
        }
        Ok(())
    }

    pub fn create_new_token(self, user_id: String) -> Result<NewApiToken> {
        self.validate()?;

        Ok(NewApiToken {
            id: Uuid::random(),
            name: self.name,
            email: self.email,
            token: Self::generate_token(),
            user_id,
        })
    }
}
