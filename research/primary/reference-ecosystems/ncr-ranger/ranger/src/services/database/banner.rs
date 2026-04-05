use super::Database;
use crate::constants::RECORD_NOT_FOUND;
use crate::models::helpers::uuid::Uuid;
use crate::models::{Banner, NewBannerWithId};
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use diesel::RunQueryDsl;

#[derive(Message)]
#[rtype(result = "Result<Banner>")]
pub struct CreateBanner(pub NewBannerWithId);

impl Handler<CreateBanner> for Database {
    type Result = ResponseActFuture<Self, Result<Banner>>;

    fn handle(&mut self, msg: CreateBanner, _ctx: &mut Self::Context) -> Self::Result {
        let new_banner = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let banner = block(move || {
                    new_banner.create_insert().execute(&mut connection)?;
                    let banner = Banner::by_id(new_banner.exercise_id).first(&mut connection)?;

                    Ok(banner)
                })
                .await??;

                Ok(banner)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Banner>")]
pub struct GetBanner(pub Uuid);

impl Handler<GetBanner> for Database {
    type Result = ResponseActFuture<Self, Result<Banner>>;

    fn handle(&mut self, msg: GetBanner, _ctx: &mut Self::Context) -> Self::Result {
        let uuid = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let banner = block(move || {
                    let banner = Banner::by_id(uuid).first(&mut connection)?;

                    Ok(banner)
                })
                .await??;

                Ok(banner)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Banner>")]
pub struct UpdateBanner(pub Uuid, pub crate::models::UpdateBanner);

impl Handler<UpdateBanner> for Database {
    type Result = ResponseActFuture<Self, Result<Banner>>;

    fn handle(&mut self, msg: UpdateBanner, _ctx: &mut Self::Context) -> Self::Result {
        let uuid = msg.0;
        let update_banner = msg.1;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let banner = block(move || {
                    let updated_rows =
                        update_banner.create_update(uuid).execute(&mut connection)?;
                    if updated_rows != 1 {
                        return Err(anyhow!(RECORD_NOT_FOUND));
                    }
                    let banner = Banner::by_id(uuid).first(&mut connection)?;
                    Ok(banner)
                })
                .await??;

                Ok(banner)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Uuid>")]
pub struct DeleteBanner(pub Uuid);

impl Handler<DeleteBanner> for Database {
    type Result = ResponseActFuture<Self, Result<Uuid>>;

    fn handle(&mut self, msg: DeleteBanner, _ctx: &mut Self::Context) -> Self::Result {
        let id = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let id = block(move || {
                    let banner = Banner::by_id(id).first(&mut connection)?;
                    banner.hard_delete().execute(&mut connection)?;
                    Ok(id)
                })
                .await??;

                Ok(id)
            }
            .into_actor(self),
        )
    }
}
