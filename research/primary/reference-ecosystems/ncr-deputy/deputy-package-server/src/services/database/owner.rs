use super::Database;
use crate::models::{NewOwner, Owner, Owners, Package};
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use diesel::RunQueryDsl;

#[derive(Message)]
#[rtype(result = "Result<Owner>")]
pub struct AddOwner {
    pub package_name: String,
    pub email: String,
}

impl Handler<AddOwner> for Database {
    type Result = ResponseActFuture<Self, Result<Owner>>;

    fn handle(&mut self, msg: AddOwner, _ctx: &mut Self::Context) -> Self::Result {
        let AddOwner {
            package_name,
            email,
        } = msg;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let owner = block(move || {
                    let package: Package = Package::by_name(package_name).first(&mut connection)?;
                    let new_owner = NewOwner::new(email, package.id);
                    new_owner.create_insert().execute(&mut connection)?;
                    let owner = Owner::by_id(new_owner.id).first(&mut connection)?;

                    Ok(owner)
                })
                .await??;
                Ok(owner)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Owners>")]
pub struct GetOwners(pub String);

impl Handler<GetOwners> for Database {
    type Result = ResponseActFuture<Self, Result<Owners>>;

    fn handle(&mut self, get_owners: GetOwners, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let GetOwners(package_name) = get_owners;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let owners = block(move || {
                    let package: Package = Package::by_name(package_name).first(&mut connection)?;
                    let owners = Owners(Owner::by_package_id(package.id).load(&mut connection)?);

                    Ok(owners)
                })
                .await??;
                Ok(owners)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<String>")]
pub struct DeleteOwner(pub String, pub String);

impl Handler<DeleteOwner> for Database {
    type Result = ResponseActFuture<Self, Result<String>>;

    fn handle(&mut self, delete_owners: DeleteOwner, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let DeleteOwner(package_name, owner_email) = delete_owners;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let owner_email = block(move || {
                    let package: Package = Package::by_name(package_name).first(&mut connection)?;
                    let owners = Owner::by_package_id(package.id).load(&mut connection)?;
                    if owners.len() == 1 {
                        return Err(anyhow!("Can not delete the last owner of a package"));
                    }
                    let owner: Owner =
                        Owner::by_email(owner_email.clone()).first(&mut connection)?;
                    owner.soft_delete().execute(&mut connection)?;

                    Ok(owner_email)
                })
                .await??;
                Ok(owner_email)
            }
            .into_actor(self),
        )
    }
}
