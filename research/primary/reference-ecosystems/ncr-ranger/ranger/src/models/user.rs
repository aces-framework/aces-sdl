use super::{helpers::uuid::Uuid, Account};
use serde::{Deserialize, Serialize};

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct User {
    pub vm_id: Uuid,
    pub accounts: Vec<UserAccount>,
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UserAccount {
    pub id: Uuid,
    pub username: String,
    pub password: Option<String>,
    pub private_key: Option<String>,
}

impl From<Account> for UserAccount {
    fn from(account: Account) -> Self {
        Self {
            id: account.id,
            username: account.username,
            password: account.password,
            private_key: account.private_key,
        }
    }
}
