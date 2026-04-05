use super::Database;
use crate::models::helpers::pagination::*;
use crate::models::helpers::uuid::Uuid;
use crate::models::{
    Category, NewCategory, NewOwner, NewPackageCategory, NewPackageVersion, Owner, Owners, Package,
    PackageCategory, PackageVersion, PackageWithVersions, PackagesWithVersionsAndPages, Version,
};
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use diesel::{OptionalExtension, RunQueryDsl};

#[derive(Message)]
#[rtype(result = "Result<PackageVersion>")]
pub struct CreatePackage(pub NewPackageVersion, pub String);

impl Handler<CreatePackage> for Database {
    type Result = ResponseActFuture<Self, Result<PackageVersion>>;

    fn handle(&mut self, msg: CreatePackage, _ctx: &mut Self::Context) -> Self::Result {
        let NewPackageVersion(mut new_package, mut new_version) = msg.0;
        new_package.name = new_package.name.to_lowercase();
        let requester_email = msg.1;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let package = block(move || {
                    let optional_package = Package::by_name(new_package.name.clone())
                        .first(&mut connection)
                        .optional()?;
                    let existing_package = match optional_package {
                        Some(package) => {
                            let owners =
                                Owners(Owner::by_package_id(package.id).load(&mut connection)?);
                            if !owners.contains_email(&requester_email) {
                                return Err(anyhow!("Requester is not an owner of this package"));
                            }
                            package
                        }
                        None => {
                            new_package.create_insert().execute(&mut connection)?;
                            let package = Package::by_id(new_package.id).first(&mut connection)?;
                            let package_owner = NewOwner::new(requester_email, package.id);
                            package_owner.create_insert().execute(&mut connection)?;
                            package
                        }
                    };
                    new_version.package_id = existing_package.id;
                    new_version.create_insert().execute(&mut connection)?;
                    let version = Version::by_id(new_version.id).first(&mut connection)?;
                    Ok(PackageVersion(existing_package, version))
                })
                .await??;
                Ok(package)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<PackagesWithVersionsAndPages>")]
pub struct GetPackages {
    pub search_term: Option<String>,
    pub package_type: Option<String>,
    pub categories: Option<Vec<String>>,
    pub paginated: bool,
    pub page: i64,
    pub per_page: i64,
    pub include_readme: bool,
}

impl Handler<GetPackages> for Database {
    type Result = ResponseActFuture<Self, Result<PackagesWithVersionsAndPages>>;

    fn handle(&mut self, search_packages: GetPackages, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let package = block(move || {
                    let search_term = search_packages.search_term.unwrap_or_default();

                    let query = match (
                        search_packages.package_type.clone(),
                        search_packages.categories,
                    ) {
                        (_, Some(search_categories)) => {
                            let search_category_ids = Category::by_names(search_categories)
                                .load(&mut connection)?
                                .iter()
                                .map(|category| category.id)
                                .collect::<Vec<Uuid>>();

                            let package_ids_by_categories =
                                PackageCategory::by_category_ids(search_category_ids)
                                    .load(&mut connection)?
                                    .iter()
                                    .map(|package_category| package_category.package_id)
                                    .collect::<Vec<Uuid>>();

                            if let Some(search_package_type) = search_packages.package_type {
                                if search_packages.paginated {
                                    Package::search_name_with_type_and_categories(
                                        search_term,
                                        search_package_type.to_lowercase(),
                                        package_ids_by_categories,
                                    )
                                    .paginate(search_packages.page)
                                    .per_page(search_packages.per_page)
                                    .load_and_count_pages(&mut connection)?
                                } else {
                                    let packages_by_type_and_category =
                                        Package::search_name_with_type_and_categories(
                                            search_term,
                                            search_package_type.to_lowercase(),
                                            package_ids_by_categories,
                                        )
                                        .load(&mut connection)?;
                                    let total_packages = packages_by_type_and_category.len();
                                    (packages_by_type_and_category, 1, total_packages as i64)
                                }
                            } else if search_packages.paginated {
                                Package::search_name_with_categories(
                                    search_term,
                                    package_ids_by_categories,
                                )
                                .paginate(search_packages.page)
                                .per_page(search_packages.per_page)
                                .load_and_count_pages(&mut connection)?
                            } else {
                                let packages_by_categories = Package::search_name_with_categories(
                                    search_term,
                                    package_ids_by_categories,
                                )
                                .load(&mut connection)?;
                                let total_packages = packages_by_categories.len();
                                (packages_by_categories, 1, total_packages as i64)
                            }
                        }
                        (Some(search_package_type), None) => {
                            if search_packages.paginated {
                                Package::search_name_with_type(
                                    search_term,
                                    search_package_type.to_lowercase(),
                                )
                                .paginate(search_packages.page)
                                .per_page(search_packages.per_page)
                                .load_and_count_pages(&mut connection)?
                            } else {
                                let packages_by_type = Package::search_name_with_type(
                                    search_term,
                                    search_package_type.to_lowercase(),
                                )
                                .load(&mut connection)?;
                                let total_packages = packages_by_type.len();
                                (packages_by_type, 1, total_packages as i64)
                            }
                        }
                        _ => {
                            if search_packages.paginated {
                                Package::search_name(search_term)
                                    .paginate(search_packages.page)
                                    .per_page(search_packages.per_page)
                                    .load_and_count_pages(&mut connection)?
                            } else {
                                let packages_by_search_term =
                                    Package::search_name(search_term).load(&mut connection)?;
                                let total_packages = packages_by_search_term.len();
                                (packages_by_search_term, 1, total_packages as i64)
                            }
                        }
                    };

                    let packages_with_versions_query_result = query
                        .0
                        .iter()
                        .map(|package| {
                            let package_versions = package
                                .versions(search_packages.include_readme)
                                .load(&mut connection)?;

                            Ok(PackageWithVersions::from((
                                package.clone(),
                                package_versions,
                            )))
                        })
                        .collect::<Result<Vec<PackageWithVersions>>>()?;

                    Ok(PackagesWithVersionsAndPages::from((
                        packages_with_versions_query_result,
                        query.1,
                        query.2,
                    )))
                })
                .await??;
                Ok(package)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Version>")]
pub struct GetPackageByNameAndVersion {
    pub name: String,
    pub version: String,
    pub include_readme: bool,
}

impl Handler<GetPackageByNameAndVersion> for Database {
    type Result = ResponseActFuture<Self, Result<Version>>;

    fn handle(
        &mut self,
        query_params: GetPackageByNameAndVersion,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let package = block(move || {
                    let package: Package = Package::by_name(query_params.name.to_lowercase())
                        .first(&mut connection)?;
                    let package_version: Version = package
                        .exact_version(query_params.version, query_params.include_readme)
                        .first(&mut connection)?;
                    Ok(package_version)
                })
                .await??;
                Ok(package)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<Version>>")]
pub struct GetVersionsByPackageName {
    pub name: String,
    pub include_readme: bool,
}

impl Handler<GetVersionsByPackageName> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<Version>>>;

    fn handle(
        &mut self,
        query_params: GetVersionsByPackageName,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let package = block(move || {
                    let package = Package::by_name(query_params.name.to_lowercase())
                        .first(&mut connection)
                        .optional()?;
                    if let Some(package) = package {
                        let package_versions: Vec<Version> = package
                            .versions(query_params.include_readme)
                            .load(&mut connection)?;
                        return Ok(package_versions);
                    }
                    Ok(Vec::new())
                })
                .await??;
                Ok(package)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Category>")]
pub struct CreateCategory(pub NewCategory, pub Uuid);

impl Handler<CreateCategory> for Database {
    type Result = ResponseActFuture<Self, Result<Category>>;

    fn handle(&mut self, msg: CreateCategory, _ctx: &mut Self::Context) -> Self::Result {
        let mut new_category: NewCategory = msg.0;
        new_category.name = new_category.name.to_lowercase();
        let package_id: Uuid = msg.1;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let category: Category = block(move || {
                    let optional_category = Category::by_name(new_category.name.clone())
                        .first(&mut connection)
                        .optional()?;
                    let existing_category = match optional_category {
                        Some(cat) => cat,
                        None => {
                            new_category.create_insert().execute(&mut connection)?;
                            Category::by_id(new_category.id).first(&mut connection)?
                        }
                    };
                    let optional_package_category = PackageCategory::by_package_and_category_id(
                        package_id,
                        existing_category.id,
                    )
                    .first(&mut connection)
                    .optional()?;
                    if optional_package_category.is_none() {
                        let new_package_category = NewPackageCategory {
                            package_id,
                            category_id: existing_category.id,
                        };
                        new_package_category
                            .create_insert()
                            .execute(&mut connection)?;
                    }
                    Ok(existing_category)
                })
                .await??;
                Ok(category)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<Category>>")]
pub struct GetAllCategories;

impl Handler<GetAllCategories> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<Category>>>;

    fn handle(&mut self, _: GetAllCategories, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let categories = block(move || {
                    let categories: Vec<Category> = Category::all().load(&mut connection)?;
                    Ok(categories)
                })
                .await??;
                Ok(categories)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<Category>>")]
pub struct GetCategoriesForPackage {
    pub id: Uuid,
}

impl Handler<GetCategoriesForPackage> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<Category>>>;

    fn handle(
        &mut self,
        query_params: GetCategoriesForPackage,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let categories = block(move || {
                    let package_categories =
                        PackageCategory::by_package_id(query_params.id).load(&mut connection)?;
                    let category_ids: Vec<Uuid> =
                        package_categories.iter().map(|pc| pc.category_id).collect();
                    let categories = Category::by_ids(category_ids).load(&mut connection)?;
                    Ok(categories)
                })
                .await??;
                Ok(categories)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Version>")]
pub struct UpdateVersionMsg {
    pub id: Uuid,
    pub version: Version,
}

impl Handler<UpdateVersionMsg> for Database {
    type Result = ResponseActFuture<Self, Result<Version>>;

    fn handle(&mut self, msg: UpdateVersionMsg, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let version = block(move || {
                    msg.version.create_update(msg.id).execute(&mut connection)?;
                    let version = Version::by_id(msg.id).first(&mut connection)?;
                    Ok(version)
                })
                .await??;
                Ok(version)
            }
            .into_actor(self),
        )
    }
}
