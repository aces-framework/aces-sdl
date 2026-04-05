use super::Database;
use crate::models::apitoken::{ApiToken, NewApiToken};
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{Ok, Result};
use diesel::RunQueryDsl;

#[derive(Message)]
#[rtype(result = "Result<ApiToken>")]
pub struct CreateApiToken(pub NewApiToken);

impl Handler<CreateApiToken> for Database {
    type Result = ResponseActFuture<Self, Result<ApiToken>>;

    fn handle(&mut self, msg: CreateApiToken, _ctx: &mut Self::Context) -> Self::Result {
        let new_api_token = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let api_token = block(move || {
                    new_api_token.create_insert().execute(&mut connection)?;
                    let api_token = ApiToken::by_id(new_api_token.id).first(&mut connection)?;
                    Ok(api_token)
                })
                .await??;
                Ok(api_token)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<ApiToken>>")]
pub struct GetApiTokens {
    pub user_id: String,
}

impl Handler<GetApiTokens> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<ApiToken>>>;

    fn handle(&mut self, get_api_tokens: GetApiTokens, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let api_tokens = block(move || {
                    let api_tokens =
                        ApiToken::by_user_id(get_api_tokens.user_id).load(&mut connection)?;
                    Ok(api_tokens)
                })
                .await??;
                Ok(api_tokens)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Option<ApiToken>>")]
pub struct GetTokenByToken(pub String);

impl Handler<GetTokenByToken> for Database {
    type Result = ResponseActFuture<Self, Result<Option<ApiToken>>>;

    fn handle(
        &mut self,
        get_api_tokens: GetTokenByToken,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let token = get_api_tokens.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let api_token = block(move || {
                    let api_tokens = ApiToken::by_token(token).load(&mut connection)?;
                    let api_token = api_tokens
                        .into_iter()
                        .collect::<Vec<ApiToken>>()
                        .first()
                        .cloned();
                    Ok(api_token)
                })
                .await??;
                Ok(api_token)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<String>")]
pub struct DeleteApiToken {
    pub user_id: String,
    pub token_id: String,
}

impl Handler<DeleteApiToken> for Database {
    type Result = ResponseActFuture<Self, Result<String>>;

    fn handle(
        &mut self,
        delete_token_info: DeleteApiToken,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let id = block(move || {
                    let api_tokens =
                        ApiToken::by_user_id(delete_token_info.user_id).load(&mut connection)?;
                    let delete_api_token = api_tokens
                        .into_iter()
                        .filter(|api_token| api_token.id.to_string() == delete_token_info.token_id)
                        .collect::<Vec<ApiToken>>()
                        .first()
                        .cloned()
                        .ok_or(anyhow::anyhow!("Token not found"))?;
                    delete_api_token.soft_delete().execute(&mut connection)?;

                    Ok(delete_token_info.token_id)
                })
                .await??;

                Ok(id)
            }
            .into_actor(self),
        )
    }
}
