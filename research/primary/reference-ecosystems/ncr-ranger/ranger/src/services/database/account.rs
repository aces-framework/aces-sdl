use super::Database;
use crate::constants::RECORD_NOT_FOUND;
use crate::models::helpers::uuid::Uuid;
use crate::models::{Account, NewAccount};
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use diesel::RunQueryDsl;

#[derive(Message)]
#[rtype(result = "Result<Account>")]
pub struct CreateAccount(pub NewAccount);

impl Handler<CreateAccount> for Database {
    type Result = ResponseActFuture<Self, Result<Account>>;

    fn handle(&mut self, msg: CreateAccount, _ctx: &mut Self::Context) -> Self::Result {
        let new_account = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let account = block(move || {
                    new_account.create_insert().execute(&mut connection)?;
                    let account = Account::by_id(new_account.id).first(&mut connection)?;

                    Ok(account)
                })
                .await??;

                Ok(account)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Account>")]
pub struct GetAccount(pub Uuid, pub String);

impl Handler<GetAccount> for Database {
    type Result = ResponseActFuture<Self, Result<Account>>;

    fn handle(&mut self, msg: GetAccount, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_shared_connection();
        let template_id = msg.0;
        let username = msg.1;

        Box::pin(
            async move {
                let account = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let account = Account::by_template_id_and_username(template_id, username)
                        .first(&mut *connection)?;

                    Ok(account)
                })
                .await?
                .map_err(|err| anyhow!("GetAccount: {err}"))?;

                Ok(account)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Account>")]
pub struct UpdateAccount(pub Uuid, pub crate::models::UpdateAccount);

impl Handler<UpdateAccount> for Database {
    type Result = ResponseActFuture<Self, Result<Account>>;

    fn handle(&mut self, msg: UpdateAccount, _ctx: &mut Self::Context) -> Self::Result {
        let uuid = msg.0;
        let update_account = msg.1;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let account = block(move || {
                    let updated_rows = update_account
                        .create_update(uuid)
                        .execute(&mut connection)?;
                    if updated_rows != 1 {
                        return Err(anyhow!(RECORD_NOT_FOUND));
                    }
                    let account = Account::by_id(uuid).first(&mut connection)?;

                    Ok(account)
                })
                .await??;

                Ok(account)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Uuid>")]
pub struct DeleteAccount(pub Uuid);

impl Handler<DeleteAccount> for Database {
    type Result = ResponseActFuture<Self, Result<Uuid>>;

    fn handle(&mut self, msg: DeleteAccount, _ctx: &mut Self::Context) -> Self::Result {
        let id = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let id = block(move || {
                    let account = Account::by_id(id).first(&mut connection)?;
                    account.soft_delete().execute(&mut connection)?;

                    Ok(id)
                })
                .await??;

                Ok(id)
            }
            .into_actor(self),
        )
    }
}
