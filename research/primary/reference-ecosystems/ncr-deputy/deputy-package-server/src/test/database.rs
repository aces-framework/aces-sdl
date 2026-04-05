use crate::models::helpers::uuid::Uuid;
use crate::models::{
    Category, NewCategory, NewOwner, NewPackageVersion, Owner, Owners, Package, PackageVersion,
    PackageWithVersions, PackagesWithVersionsAndPages, Version,
};
use crate::services::database::owner::{AddOwner, DeleteOwner, GetOwners};
use crate::services::database::package::{
    CreateCategory, CreatePackage, GetAllCategories, GetCategoriesForPackage,
    GetPackageByNameAndVersion, GetPackages, GetVersionsByPackageName, UpdateVersionMsg,
};
use actix::Actor;
use actix::ActorFutureExt;
use actix::{Handler, ResponseActFuture, WrapFuture};
use anyhow::{anyhow, Ok, Result};
use chrono::NaiveDateTime;
use std::collections::HashMap;

#[derive(Default, Clone, Debug)]
pub struct MockDatabase {
    packages: HashMap<Uuid, Package>,
    package_versions: HashMap<Uuid, Vec<Version>>,
    categories: HashMap<Uuid, Category>,
    package_categories: HashMap<Uuid, Vec<Uuid>>,
    owners: HashMap<Uuid, Owner>,
}

impl Actor for MockDatabase {
    type Context = actix::Context<Self>;
}

impl From<NewPackageVersion> for PackageVersion {
    fn from(NewPackageVersion(new_package, new_version): NewPackageVersion) -> Self {
        let package = Package {
            id: new_package.id,
            package_type: new_package.package_type,
            created_at: NaiveDateTime::MAX,
            updated_at: NaiveDateTime::MAX,
            deleted_at: None,
            name: new_package.name.to_lowercase(),
        };
        let version = Version {
            id: Uuid::random().to_owned(),
            created_at: NaiveDateTime::MAX,
            updated_at: NaiveDateTime::MAX,
            deleted_at: None,
            package_id: new_package.id,
            version: new_version.version,
            description: new_version.description,
            license: new_version.license,
            is_yanked: new_version.is_yanked,
            readme_html: new_version.readme_html,
            package_size: new_version.package_size,
            checksum: new_version.checksum,
        };
        Self(package, version)
    }
}

impl Handler<CreatePackage> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<PackageVersion>>;

    fn handle(&mut self, msg: CreatePackage, _ctx: &mut Self::Context) -> Self::Result {
        Box::pin(
            async move { msg }
                .into_actor(self)
                .map(move |msg, mock_database, _| {
                    let new_package_version = msg.0;
                    let PackageVersion(new_package, version) = new_package_version.into();
                    let requester_email = msg.1;

                    let optional_package = mock_database
                        .packages
                        .values()
                        .find(|package| package.name == new_package.name);

                    match optional_package {
                        Some(package) => {
                            let owners = mock_database
                                .owners
                                .values()
                                .filter_map(|owner| {
                                    if owner.package_id == package.id {
                                        Some(owner.clone())
                                    } else {
                                        None
                                    }
                                })
                                .collect::<Vec<_>>();
                            if !Owners(owners).contains_email(&requester_email) {
                                return Err(anyhow!("Requester is not an owner of this package"));
                            }
                        }
                        None => {
                            let new_owner = NewOwner::new(requester_email, new_package.id);
                            let owner = Owner::from(new_owner);
                            mock_database
                                .packages
                                .insert(new_package.id, new_package.clone());
                            mock_database.owners.insert(Uuid::random(), owner);
                        }
                    }

                    mock_database
                        .package_versions
                        .entry(new_package.id)
                        .or_default()
                        .push(version.clone());
                    Ok(PackageVersion(new_package, version))
                }),
        )
    }
}

impl Handler<GetPackages> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<PackagesWithVersionsAndPages>>;

    fn handle(&mut self, msg: GetPackages, _ctx: &mut Self::Context) -> Self::Result {
        Box::pin(
            async move {}
                .into_actor(self)
                .map(move |_, mock_database, _| {
                    let search_term = msg.search_term.unwrap_or_default();

                    let mut packages: Vec<Package> =
                        mock_database.packages.values().cloned().collect();

                    packages.retain(|package| {
                        package.name.to_lowercase().contains(search_term.as_str())
                    });

                    packages = match (msg.package_type.clone(), msg.categories) {
                        (_, Some(search_categories)) => {
                            let search_category_ids: Vec<Uuid> = mock_database
                                .categories
                                .values()
                                .filter(|category| {
                                    search_categories
                                        .clone()
                                        .contains(&category.name.to_lowercase())
                                })
                                .map(|category| category.id)
                                .collect();

                            let package_ids_by_categories: Vec<Uuid> = mock_database
                                .package_categories
                                .iter()
                                .filter(|(_package_id, category_ids)| {
                                    search_category_ids
                                        .iter()
                                        .any(|category_id| category_ids.contains(category_id))
                                })
                                .map(|(package_id, _category_ids)| package_id.to_owned())
                                .collect();

                            packages
                                .retain(|package| package_ids_by_categories.contains(&package.id));

                            if let Some(search_package_type) = msg.package_type {
                                packages.retain(|package| {
                                    package
                                        .package_type
                                        .eq_ignore_ascii_case(search_package_type.as_str())
                                });
                            }
                            packages
                        }
                        (Some(search_package_type), None) => {
                            packages.retain(|package| {
                                package
                                    .package_type
                                    .eq_ignore_ascii_case(search_package_type.as_str())
                            });
                            packages
                        }
                        _ => packages,
                    };

                    let packages_with_versions: Vec<PackageWithVersions> = packages
                        .into_iter()
                        .map(|package| {
                            let versions = mock_database
                                .package_versions
                                .get(&package.id)
                                .ok_or(anyhow::anyhow!("Package not found"))?
                                .to_owned();
                            Ok(PackageWithVersions::from((package, versions)))
                        })
                        .collect::<Result<Vec<PackageWithVersions>>>()?;

                    let packages_with_versions_and_pages = PackagesWithVersionsAndPages::from((
                        packages_with_versions,
                        rand::random::<i64>(),
                        rand::random::<i64>(),
                    ));

                    Ok(packages_with_versions_and_pages)
                }),
        )
    }
}

impl Handler<GetPackageByNameAndVersion> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<Version>>;

    fn handle(
        &mut self,
        msg: GetPackageByNameAndVersion,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let name = msg.name.to_lowercase();
        let version_value = msg.version;
        Box::pin(async move { (name, version_value) }.into_actor(self).map(
            move |(name, version_value), mock_database, _| {
                let packages: Vec<Package> = mock_database.packages.values().cloned().collect();

                let package = packages
                    .into_iter()
                    .find(|package| package.name == name)
                    .ok_or(anyhow::anyhow!("Package not found"))?;

                let version = mock_database
                    .package_versions
                    .get(&package.id)
                    .ok_or(anyhow::anyhow!("Package not found"))?
                    .iter()
                    .find(|version| version.version == version_value)
                    .ok_or(anyhow::anyhow!("Package not found"))?
                    .clone();
                Ok(version)
            },
        ))
    }
}

impl Handler<GetVersionsByPackageName> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<Vec<Version>>>;

    fn handle(&mut self, msg: GetVersionsByPackageName, _ctx: &mut Self::Context) -> Self::Result {
        let name = msg.name.to_lowercase();
        Box::pin(
            async move { name }
                .into_actor(self)
                .map(move |name, mock_database, _| {
                    let packages: Vec<Package> = mock_database.packages.values().cloned().collect();

                    let package = packages.into_iter().find(|package| package.name == name);

                    if let Some(package) = package {
                        let versions = mock_database
                            .package_versions
                            .get(&package.id)
                            .ok_or(anyhow::anyhow!("Package not found"))?
                            .to_owned();

                        return Ok(versions);
                    }

                    Ok(vec![])
                }),
        )
    }
}

impl Handler<CreateCategory> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<Category>>;

    fn handle(&mut self, msg: CreateCategory, _ctx: &mut Self::Context) -> Self::Result {
        let new_category: NewCategory = msg.0;

        Box::pin(async move { new_category }.into_actor(self).map(
            move |new_category, mock_database, _| {
                let category = Category {
                    id: new_category.id,
                    name: new_category.name.to_lowercase(),
                    created_at: Default::default(),
                    updated_at: Default::default(),
                    deleted_at: None,
                };
                mock_database
                    .categories
                    .insert(category.id, category.clone());
                mock_database
                    .package_categories
                    .entry(msg.1)
                    .or_default()
                    .push(category.id);

                Ok(category)
            },
        ))
    }
}

impl From<NewOwner> for Owner {
    fn from(new_owner: NewOwner) -> Self {
        Self {
            id: new_owner.id,
            email: new_owner.email,
            package_id: new_owner.package_id,
            created_at: Default::default(),
            updated_at: Default::default(),
            deleted_at: Default::default(),
        }
    }
}

impl Handler<AddOwner> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<Owner>>;

    fn handle(&mut self, msg: AddOwner, _ctx: &mut Self::Context) -> Self::Result {
        let AddOwner {
            mut package_name,
            email,
        } = msg;
        package_name = package_name.to_lowercase();

        Box::pin(
            async move { email }
                .into_actor(self)
                .map(move |email, mock_database, _| {
                    let package = mock_database
                        .packages
                        .values()
                        .find(|package| package.name == package_name)
                        .ok_or(anyhow::anyhow!("Mock Package not found"))?;

                    let new_owner = NewOwner::new(email, package.id);
                    let owner = Owner::from(new_owner);
                    mock_database.owners.insert(owner.id, owner.clone());
                    Ok(owner)
                }),
        )
    }
}

impl Handler<GetOwners> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<Owners>>;

    fn handle(&mut self, get_owners: GetOwners, _ctx: &mut Self::Context) -> Self::Result {
        Box::pin(async move { get_owners.0 }.into_actor(self).map(
            move |package_name, mock_database, _| {
                let package = mock_database
                    .packages
                    .values()
                    .find(|package| package.name == package_name.to_lowercase())
                    .ok_or(anyhow::anyhow!("Mock Package not found"))?;

                let owners = mock_database
                    .owners
                    .values()
                    .filter_map(|owner| {
                        if owner.package_id == package.id {
                            Some(owner.clone())
                        } else {
                            None
                        }
                    })
                    .collect::<Vec<_>>();

                Ok(Owners(owners))
            },
        ))
    }
}

impl Handler<DeleteOwner> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<String>>;

    fn handle(&mut self, delete_owners: DeleteOwner, _ctx: &mut Self::Context) -> Self::Result {
        let DeleteOwner(mut package_name, owner_email) = delete_owners;
        package_name = package_name.to_lowercase();

        Box::pin(
            async move {}
                .into_actor(self)
                .map(move |_, mock_database, _| {
                    let package = mock_database
                        .packages
                        .values()
                        .find(|package| package.name == package_name)
                        .ok_or(anyhow::anyhow!("Mock Package not found"))?;

                    let owners = mock_database
                        .owners
                        .values()
                        .filter_map(|owner| {
                            if owner.package_id == package.id {
                                Some(owner.clone())
                            } else {
                                None
                            }
                        })
                        .collect::<Vec<_>>();

                    if owners.len() == 1 {
                        return Err(anyhow!("Can not delete the last owner of a package"));
                    }

                    let owner_to_delete = owners
                        .into_iter()
                        .find(|owner| owner.email == owner_email)
                        .ok_or(anyhow!("Mock Owner not found among package owners"))?;

                    let deleted_owner = mock_database.owners.remove(&owner_to_delete.id);
                    match deleted_owner {
                        Some(owner) => Ok(owner.email),
                        None => Err(anyhow!("Mock Owner not found in database")),
                    }
                }),
        )
    }
}

impl Handler<UpdateVersionMsg> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<Version>>;

    fn handle(&mut self, msg: UpdateVersionMsg, _ctx: &mut Self::Context) -> Self::Result {
        Box::pin(
            async move { msg }
                .into_actor(self)
                .map(move |msg, mock_database, _| {
                    let version = msg.version;
                    let versions = mock_database
                        .package_versions
                        .get_mut(&version.package_id)
                        .ok_or(anyhow::anyhow!("Package not found"))?;
                    let index = versions
                        .iter()
                        .position(|v| v.id == version.id)
                        .ok_or(anyhow::anyhow!("Version not found"))?;
                    versions[index] = version.clone();
                    Ok(version)
                }),
        )
    }
}

impl Handler<GetCategoriesForPackage> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<Vec<Category>>>;

    fn handle(
        &mut self,
        query_params: GetCategoriesForPackage,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let db_categories = self.categories.clone();
        let db_package_categories = self.package_categories.clone();
        Box::pin(async move { query_params }.into_actor(self).map(
            move |query_params, _mock_database, _| {
                let package_categories: HashMap<Uuid, Vec<Uuid>> = db_package_categories
                    .into_iter()
                    .filter(|(package_id, _category_ids)| *package_id == query_params.id)
                    .collect();
                let categories: Vec<Category> = db_categories
                    .values()
                    .filter(|category| {
                        package_categories
                            .values()
                            .any(|category_ids| category_ids.contains(&category.id))
                    })
                    .cloned()
                    .collect();
                Ok(categories)
            },
        ))
    }
}

impl Handler<GetAllCategories> for MockDatabase {
    type Result = ResponseActFuture<Self, Result<Vec<Category>>>;

    fn handle(&mut self, _msg: GetAllCategories, _ctx: &mut Self::Context) -> Self::Result {
        let db_categories = self.categories.clone();

        Box::pin(
            async move { _msg }
                .into_actor(self)
                .map(move |_msg, _mock_database, _| {
                    let categories: Vec<Category> = db_categories.values().cloned().collect();
                    Ok(categories)
                }),
        )
    }
}
