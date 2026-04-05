use crate::models::helpers::uuid::Uuid;
use crate::services::database::{
    FilterByNames, SearchLikeName, SearchLikeNameAndIds, SearchLikeNameAndType,
    SearchLikeNameAndTypeAndIds,
};
use crate::{
    schema::{categories, package_categories, packages, versions},
    services::database::{All, Create, FilterByIds, FilterExisting, SelectById, UpdateById},
};
use chrono::NaiveDateTime;
use deputy_library::package::PackageMetadata;
use deputy_library::rest::{
    PackageWithVersionsRest, PackagesWithVersionsAndPagesRest, VersionRest,
};
use diesel::{
    dsl::sql, helper_types::FindBy, insert_into, mysql::Mysql, prelude::*, sql_types::Text,
};
use serde::{Deserialize, Serialize};

#[derive(
    Queryable,
    QueryableByName,
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
#[diesel(table_name = categories)]
#[serde(rename_all = "camelCase")]
pub struct Category {
    pub id: Uuid,
    pub name: String,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub deleted_at: Option<NaiveDateTime>,
}

impl Category {
    fn all_with_deleted() -> All<categories::table, Self> {
        categories::table.select(Self::as_select())
    }

    pub fn all() -> FilterExisting<All<categories::table, Self>, categories::deleted_at> {
        Self::all_with_deleted().filter(categories::deleted_at.is_null())
    }

    pub fn by_id(
        id: Uuid,
    ) -> FindBy<
        FilterExisting<All<categories::table, Self>, categories::deleted_at>,
        categories::id,
        Uuid,
    > {
        Self::all().filter(categories::id.eq(id))
    }

    pub fn by_name(
        name: String,
    ) -> FindBy<
        FilterExisting<All<categories::table, Self>, categories::deleted_at>,
        categories::name,
        String,
    > {
        Self::all().filter(categories::name.eq(name))
    }

    pub fn by_ids(
        category_ids: Vec<Uuid>,
    ) -> FilterByIds<categories::table, categories::id, categories::deleted_at, Self> {
        Self::all().filter(categories::id.eq_any(category_ids))
    }

    pub fn by_names(
        category_names: Vec<String>,
    ) -> FilterByNames<categories::table, categories::name, categories::deleted_at, Self> {
        Self::all().filter(categories::name.eq_any(category_names))
    }
}

#[derive(
    Queryable, Selectable, Insertable, Clone, Debug, Eq, PartialEq, Deserialize, Serialize,
)]
#[diesel(table_name = categories)]
#[serde(rename_all = "camelCase")]
pub struct NewCategory {
    pub id: Uuid,
    pub name: String,
}

impl NewCategory {
    pub fn create_insert(&self) -> Create<&Self, categories::table> {
        insert_into(categories::table).values(self)
    }
}

#[derive(
    Queryable, Selectable, Insertable, Clone, Debug, Eq, PartialEq, Deserialize, Serialize,
)]
#[diesel(belongs_to(Package, foreign_key = package_id))]
#[diesel(belongs_to(Category, foreign_key = category_id))]
#[diesel(table_name = package_categories)]
#[serde(rename_all = "camelCase")]
pub struct NewPackageCategory {
    pub package_id: Uuid,
    pub category_id: Uuid,
}

impl NewPackageCategory {
    pub fn create_insert(&self) -> Create<&Self, package_categories::table> {
        insert_into(package_categories::table).values(self)
    }
}

#[derive(
    Associations, Clone, Queryable, QueryableByName, Selectable, Debug, Deserialize, Serialize,
)]
#[diesel(belongs_to(Package, foreign_key = package_id))]
#[diesel(belongs_to(Category, foreign_key = category_id))]
#[diesel(table_name = package_categories)]
#[serde(rename_all = "camelCase")]
pub struct PackageCategory {
    pub package_id: Uuid,
    pub category_id: Uuid,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub deleted_at: Option<NaiveDateTime>,
}

impl PackageCategory {
    fn all_with_deleted() -> All<package_categories::table, Self> {
        package_categories::table.select(Self::as_select())
    }

    pub fn all(
    ) -> FilterExisting<All<package_categories::table, Self>, package_categories::deleted_at> {
        Self::all_with_deleted().filter(package_categories::deleted_at.is_null())
    }

    pub fn by_package_id(
        id: Uuid,
    ) -> SelectById<
        package_categories::table,
        package_categories::package_id,
        package_categories::deleted_at,
        Self,
    > {
        Self::all().filter(package_categories::package_id.eq(id))
    }

    pub fn by_category_ids(
        category_ids: Vec<Uuid>,
    ) -> FilterByIds<
        package_categories::table,
        package_categories::category_id,
        package_categories::deleted_at,
        Self,
    > {
        Self::all().filter(package_categories::category_id.eq_any(category_ids))
    }

    pub fn by_package_and_category_id(
        package_id: Uuid,
        category_id: Uuid,
    ) -> FindBy<
        SelectById<
            package_categories::table,
            package_categories::package_id,
            package_categories::deleted_at,
            Self,
        >,
        package_categories::category_id,
        Uuid,
    > {
        Self::all()
            .filter(package_categories::package_id.eq(package_id))
            .filter(package_categories::category_id.eq(category_id))
    }
}

#[derive(
    AsChangeset,
    Associations,
    Clone,
    Queryable,
    QueryableByName,
    Selectable,
    Identifiable,
    Debug,
    Deserialize,
    Serialize,
)]
#[diesel(belongs_to(Package, foreign_key = package_id))]
#[diesel(table_name = versions)]
#[serde(rename_all = "camelCase")]
pub struct Version {
    pub id: Uuid,
    pub package_id: Uuid,
    pub version: String,
    pub description: String,
    pub license: String,
    pub is_yanked: bool,
    pub readme_html: String,
    pub package_size: u64,
    pub checksum: String,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub deleted_at: Option<NaiveDateTime>,
}

impl Version {
    pub fn by_id(
        id: Uuid,
    ) -> FindBy<FilterExisting<All<versions::table, Self>, versions::deleted_at>, versions::id, Uuid>
    {
        Self::all().filter(versions::id.eq(id))
    }

    fn all_with_deleted() -> All<versions::table, Self> {
        versions::table.select(Self::as_select())
    }

    pub fn all() -> FilterExisting<All<versions::table, Self>, versions::deleted_at> {
        Self::all_with_deleted().filter(versions::deleted_at.is_null())
    }

    pub fn create_update(&self, id: Uuid) -> UpdateById<versions::id, versions::table, &Self> {
        diesel::update(versions::table)
            .filter(versions::id.eq(id))
            .set(self)
    }
}

#[derive(
    Queryable,
    QueryableByName,
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
#[diesel(table_name = packages)]
#[serde(rename_all = "camelCase")]
pub struct Package {
    pub id: Uuid,
    pub name: String,
    pub package_type: String,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub deleted_at: Option<NaiveDateTime>,
}

impl Package {
    fn all_with_deleted() -> All<packages::table, Self> {
        packages::table.select(Self::as_select())
    }

    fn all() -> FilterExisting<All<packages::table, Self>, packages::deleted_at> {
        Self::all_with_deleted().filter(packages::deleted_at.is_null())
    }

    pub fn search_name(
        search_term: String,
    ) -> SearchLikeName<packages::table, packages::name, packages::deleted_at, Self> {
        Self::all().filter(packages::name.like(format!("%{}%", search_term)))
    }

    pub fn search_name_with_type(
        search_term: String,
        package_type: String,
    ) -> SearchLikeNameAndType<
        packages::table,
        packages::name,
        packages::package_type,
        packages::deleted_at,
        Self,
    > {
        Self::search_name(search_term).filter(packages::package_type.eq(package_type))
    }

    pub fn search_name_with_categories(
        search_term: String,
        package_ids_by_categories: Vec<Uuid>,
    ) -> SearchLikeNameAndIds<
        packages::table,
        packages::name,
        packages::id,
        packages::deleted_at,
        Self,
    > {
        Self::search_name(search_term).filter(packages::id.eq_any(package_ids_by_categories))
    }

    pub fn search_name_with_type_and_categories(
        search_term: String,
        package_type: String,
        package_ids_by_categories: Vec<Uuid>,
    ) -> SearchLikeNameAndTypeAndIds<
        packages::table,
        packages::name,
        packages::package_type,
        packages::id,
        packages::deleted_at,
        Self,
    > {
        Self::search_name_with_type(search_term, package_type)
            .filter(packages::id.eq_any(package_ids_by_categories))
    }

    pub fn by_id(
        id: Uuid,
    ) -> FindBy<FilterExisting<All<packages::table, Self>, packages::deleted_at>, packages::id, Uuid>
    {
        Self::all().filter(packages::id.eq(id))
    }

    pub fn by_name(
        name: String,
    ) -> FindBy<
        FilterExisting<All<packages::table, Self>, packages::deleted_at>,
        packages::name,
        String,
    > {
        Self::all().filter(packages::name.eq(name))
    }

    pub fn versions(&self, include_readme: bool) -> versions::BoxedQuery<'_, Mysql> {
        let mut query = Version::belonging_to(self).into_boxed();

        if !include_readme {
            query = query.select((
                versions::id,
                versions::package_id,
                versions::version,
                versions::description,
                versions::license,
                versions::is_yanked,
                sql::<Text>("''").into_sql::<Text>(),
                versions::package_size,
                versions::checksum,
                versions::created_at,
                versions::updated_at,
                versions::deleted_at,
            ));
        }

        query
    }

    pub fn exact_version(
        &self,
        version: String,
        include_readme: bool,
    ) -> FindBy<versions::BoxedQuery<'_, Mysql>, versions::version, String> {
        self.versions(include_readme)
            .filter(versions::version.eq(version))
    }
}

pub struct PackageVersion(pub Package, pub Version);

#[derive(
    Queryable, Selectable, Insertable, Clone, Debug, Eq, PartialEq, Deserialize, Serialize,
)]
#[diesel(table_name = packages)]
#[serde(rename_all = "camelCase")]
pub struct NewPackage {
    pub id: Uuid,
    pub name: String,
    pub package_type: String,
}

impl NewPackage {
    pub fn create_insert(&self) -> Create<&Self, packages::table> {
        insert_into(packages::table).values(self)
    }
}

#[derive(
    Queryable, Selectable, Insertable, Clone, Debug, Eq, PartialEq, Deserialize, Serialize,
)]
#[diesel(table_name = versions)]
#[serde(rename_all = "camelCase")]
pub struct NewVersion {
    pub id: Uuid,
    pub version: String,
    pub description: String,
    pub license: String,
    pub is_yanked: bool,
    pub readme_html: String,
    pub package_size: u64,
    pub checksum: String,
    pub package_id: Uuid,
}

impl NewVersion {
    pub fn create_insert(&self) -> Create<&Self, versions::table> {
        insert_into(versions::table).values(self)
    }
}

pub struct NewPackageVersion(pub NewPackage, pub NewVersion);

impl From<(PackageMetadata, String)> for NewPackageVersion {
    fn from((package_metadata, readme_html): (PackageMetadata, String)) -> Self {
        let package = NewPackage {
            id: Uuid::random().to_owned(),
            name: package_metadata.name,
            package_type: package_metadata.package_type.to_string(),
        };
        let version = NewVersion {
            id: Uuid::random().to_owned(),
            version: package_metadata.version,
            description: package_metadata.description,
            license: package_metadata.license,
            is_yanked: false,
            readme_html,
            package_size: package_metadata.package_size,
            checksum: package_metadata.checksum,
            package_id: package.id,
        };

        NewPackageVersion(package, version)
    }
}

impl From<Version> for VersionRest {
    fn from(version: Version) -> Self {
        Self {
            id: version.id.into(),
            package_id: version.package_id.into(),
            version: version.version,
            description: version.description,
            license: version.license,
            is_yanked: version.is_yanked,
            readme_html: match version.readme_html.trim().is_empty() {
                true => None,
                false => Some(version.readme_html),
            },
            package_size: version.package_size,
            checksum: version.checksum,
            created_at: version.created_at,
            updated_at: version.updated_at,
        }
    }
}

impl From<String> for NewCategory {
    fn from(category: String) -> Self {
        Self {
            id: Uuid::random().to_owned(),
            name: category,
        }
    }
}

#[derive(Deserialize, Serialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct PackageWithVersions {
    pub id: Uuid,
    pub name: String,
    pub package_type: String,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub versions: Vec<Version>,
}

impl From<(Package, Vec<Version>)> for PackageWithVersions {
    fn from((package, versions): (Package, Vec<Version>)) -> Self {
        Self {
            id: package.id,
            name: package.name,
            package_type: package.package_type,
            created_at: package.created_at,
            updated_at: package.updated_at,
            versions,
        }
    }
}

impl From<PackageWithVersions> for PackageWithVersionsRest {
    fn from(package: PackageWithVersions) -> Self {
        Self {
            id: package.id.into(),
            name: package.name,
            package_type: package.package_type,
            created_at: package.created_at,
            updated_at: package.updated_at,
            versions: package
                .versions
                .into_iter()
                .map(VersionRest::from)
                .collect(),
        }
    }
}

#[derive(Deserialize, Serialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct PackagesWithVersionsAndPages {
    pub packages: Vec<PackageWithVersions>,
    pub total_pages: i64,
    pub total_packages: i64,
}

impl From<(Vec<PackageWithVersions>, i64, i64)> for PackagesWithVersionsAndPages {
    fn from((packages, total_pages, total_packages): (Vec<PackageWithVersions>, i64, i64)) -> Self {
        Self {
            packages,
            total_pages,
            total_packages,
        }
    }
}

impl From<PackagesWithVersionsAndPages> for PackagesWithVersionsAndPagesRest {
    fn from(packages_with_versions_and_pages: PackagesWithVersionsAndPages) -> Self {
        Self {
            packages: packages_with_versions_and_pages
                .packages
                .into_iter()
                .map(PackageWithVersionsRest::from)
                .collect(),
            total_pages: packages_with_versions_and_pages.total_pages,
            total_packages: packages_with_versions_and_pages.total_packages,
        }
    }
}
