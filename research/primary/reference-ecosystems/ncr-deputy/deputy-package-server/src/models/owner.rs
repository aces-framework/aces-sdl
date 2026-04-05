use crate::constants::NAIVEDATETIME_DEFAULT_VALUE;
use crate::models::helpers::uuid::Uuid;
use crate::services::database::{FilterExistingNotNull, SoftDeleteById};
use crate::{
    schema::owners,
    services::database::{All, Create},
};
use chrono::NaiveDateTime;
use diesel::{
    helper_types::FindBy, insert_into, ExpressionMethods, Identifiable, Insertable, QueryDsl,
    Queryable, Selectable, SelectableHelper,
};
use serde::{Deserialize, Serialize};

#[derive(
    Queryable,
    Identifiable,
    Selectable,
    Insertable,
    Clone,
    Debug,
    Eq,
    PartialEq,
    Deserialize,
    Serialize,
)]
#[diesel(table_name = owners)]
#[serde(rename_all = "camelCase")]
pub struct Owner {
    pub id: Uuid,
    pub email: String,
    pub package_id: Uuid,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub deleted_at: NaiveDateTime,
}

#[derive(Deserialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct OwnerQuery {
    pub email: String,
}

impl Owner {
    fn all_with_deleted() -> All<owners::table, Self> {
        owners::table.select(Self::as_select())
    }

    pub fn all() -> FilterExistingNotNull<All<owners::table, Self>, owners::deleted_at> {
        Self::all_with_deleted().filter(owners::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(
        id: Uuid,
    ) -> FindBy<FilterExistingNotNull<All<owners::table, Self>, owners::deleted_at>, owners::id, Uuid>
    {
        Self::all().filter(owners::id.eq(id))
    }

    pub fn by_package_id(
        id: Uuid,
    ) -> FindBy<
        FilterExistingNotNull<All<owners::table, Self>, owners::deleted_at>,
        owners::package_id,
        Uuid,
    > {
        Self::all().filter(owners::package_id.eq(id))
    }

    pub fn by_email(
        email: String,
    ) -> FindBy<
        FilterExistingNotNull<All<owners::table, Self>, owners::deleted_at>,
        owners::email,
        String,
    > {
        Self::all().filter(owners::email.eq(email))
    }

    pub fn soft_delete(&self) -> SoftDeleteById<owners::id, owners::deleted_at, owners::table> {
        diesel::update(owners::table.filter(owners::id.eq(self.id)))
            .set(owners::deleted_at.eq(diesel::dsl::now))
    }
}

#[derive(
    Queryable, Selectable, Insertable, Clone, Debug, Eq, PartialEq, Deserialize, Serialize,
)]
#[diesel(table_name = owners)]
#[serde(rename_all = "camelCase")]
pub struct NewOwner {
    pub id: Uuid,
    pub email: String,
    pub package_id: Uuid,
}

impl NewOwner {
    pub fn new(email: String, package_id: Uuid) -> Self {
        Self {
            id: Uuid::random(),
            email: email.to_ascii_lowercase(),
            package_id,
        }
    }

    pub fn create_insert(&self) -> Create<&Self, owners::table> {
        insert_into(owners::table).values(self)
    }
}
#[derive(Deserialize, Serialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Owners(pub Vec<Owner>);

impl Owners {
    pub fn into_inner(self) -> Vec<Owner> {
        self.0
    }

    pub fn iter(&self) -> impl Iterator<Item = &Owner> {
        self.0.iter()
    }

    pub fn len(&self) -> usize {
        self.0.len()
    }

    pub fn is_empty(&self) -> bool {
        self.iter().count() == 0
    }

    pub fn contains_email(&self, email: &str) -> bool {
        self.iter().any(|owner| owner.email == email)
    }
}
