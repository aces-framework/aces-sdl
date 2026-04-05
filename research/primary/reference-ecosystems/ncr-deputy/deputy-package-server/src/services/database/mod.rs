pub(crate) mod apitoken;
pub(crate) mod owner;
pub(crate) mod package;

use crate::models::helpers::uuid::Uuid;
use crate::utilities::run_migrations;
use actix::Actor;
use anyhow::{anyhow, Result};
use chrono::NaiveDateTime;
use diesel::{
    dsl::now,
    helper_types::{AsSelect, Eq, EqAny, Filter, IsNull, Like, Select, Update},
    mysql::{Mysql, MysqlConnection},
    query_builder::InsertStatement,
    r2d2::{ConnectionManager, Pool, PooledConnection},
    Insertable,
};

pub type All<Table, T> = Select<Table, AsSelect<T, Mysql>>;
pub type FilterExisting<Target, DeletedAtColumn> = Filter<Target, IsNull<DeletedAtColumn>>;
pub type FilterExistingNotNull<Target, DeletedAtColumn> =
    Filter<Target, Eq<DeletedAtColumn, NaiveDateTime>>;
pub type ById<Id, R> = Filter<R, Eq<Id, Uuid>>;
pub type SelectById<Table, Id, DeletedAtColumn, T> =
    ById<Id, FilterExisting<All<Table, T>, DeletedAtColumn>>;
pub type Create<Type, Table> = InsertStatement<Table, <Type as Insertable<Table>>::Values>;
pub type UpdateById<Id, Table, T> = Update<ById<Id, Table>, T>;
pub type FilterByIds<Table, Id, DeletedAtColumn, T> =
    Filter<FilterExisting<All<Table, T>, DeletedAtColumn>, EqAny<Id, Vec<Uuid>>>;
pub type FilterByNames<Table, Name, DeletedAtColumn, T> =
    Filter<FilterExisting<All<Table, T>, DeletedAtColumn>, EqAny<Name, Vec<String>>>;
type UpdateDeletedAt<DeletedAtColumn> = Eq<DeletedAtColumn, now>;
pub type SoftDelete<L, DeletedAtColumn> = Update<L, UpdateDeletedAt<DeletedAtColumn>>;
pub type SoftDeleteById<Id, DeleteAtColumn, Table> = SoftDelete<ById<Id, Table>, DeleteAtColumn>;
pub type SearchLikeName<Table, Name, DeletedAtColumn, T> =
    Filter<FilterExisting<All<Table, T>, DeletedAtColumn>, Like<Name, String>>;
pub type SearchLikeNameAndType<Table, Name, Type, DeletedAtColumn, T> =
    Filter<SearchLikeName<Table, Name, DeletedAtColumn, T>, Eq<Type, String>>;
pub type SearchLikeNameAndIds<Table, Name, Id, DeletedAtColumn, T> =
    Filter<SearchLikeName<Table, Name, DeletedAtColumn, T>, EqAny<Id, Vec<Uuid>>>;
pub type SearchLikeNameAndTypeAndIds<Table, Name, Type, Id, DeletedAtColumn, T> =
    Filter<SearchLikeNameAndType<Table, Name, Type, DeletedAtColumn, T>, EqAny<Id, Vec<Uuid>>>;

#[derive(Clone)]
pub struct Database {
    connection_pool: Pool<ConnectionManager<MysqlConnection>>,
}

impl Actor for Database {
    type Context = actix::Context<Self>;
}

impl Database {
    pub fn try_new(database_url: &str) -> Result<Self> {
        let manager = ConnectionManager::<MysqlConnection>::new(database_url);
        let connection_pool = Pool::builder()
            .build(manager)
            .map_err(|error| anyhow!("Failed to create database connection pool: {}", error))?;
        let mut connection = connection_pool
            .get()
            .map_err(|error| anyhow!("Failed to get database connection: {}", error))?;
        run_migrations(&mut connection)
            .map_err(|error| anyhow!("Failed to run database migrations: {}", error))?;
        Ok(Self { connection_pool })
    }

    pub fn get_connection(&self) -> Result<PooledConnection<ConnectionManager<MysqlConnection>>> {
        Ok(self.connection_pool.get()?)
    }
}
