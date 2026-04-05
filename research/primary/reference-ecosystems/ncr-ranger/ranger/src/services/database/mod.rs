pub(crate) mod account;
pub(crate) mod banner;
pub(crate) mod condition;
pub(crate) mod deployment;
pub(crate) mod email;
pub(crate) mod email_status;
pub(crate) mod event;
pub(crate) mod event_info;
pub(crate) mod exercise;
pub(crate) mod metric;
pub(crate) mod order;
pub(crate) mod participant;
pub(crate) mod upload;

use crate::{models::helpers::uuid::Uuid, utilities::run_migrations};
use actix::{Actor, Addr};
use anyhow::{anyhow, Result};
use chrono::NaiveDateTime;
use diesel::{
    dsl::now,
    helper_types::{AsSelect, Eq, Filter, Select, Update},
    mysql::{Mysql, MysqlConnection},
    query_builder::{
        DeleteStatement, InsertOrIgnoreStatement, InsertStatement, IntoUpdateTarget,
        ReplaceStatement,
    },
    r2d2::{ConnectionManager, Pool, PooledConnection},
    sql_function, Insertable,
};
use std::sync::{Arc, Mutex};

use super::websocket::WebSocketManager;

sql_function! (fn current_timestamp() -> Timestamp);

pub type All<Table, T> = Select<Table, AsSelect<T, Mysql>>;
pub type FilterExisting<Target, DeletedAtColumn> =
    Filter<Target, Eq<DeletedAtColumn, NaiveDateTime>>;
pub type ById<Id, R> = Filter<R, Eq<Id, Uuid>>;
pub type ByIdRefernce<'a, Id, R> = Filter<R, Eq<Id, &'a Uuid>>;
pub type ByName<Name, R> = Filter<R, Eq<Name, String>>;
pub type ByTemplateId<TemplateId, R> = Filter<R, Eq<TemplateId, Uuid>>;
pub type ByDeploymentId<DeploymentId, R> = Filter<R, Eq<DeploymentId, Uuid>>;
pub type ByUsername<Username, R> = Filter<R, Eq<Username, String>>;
pub type SelectByIdFromAll<Table, Id, T> = ById<Id, All<Table, T>>;
pub type SelectByIdFromAllReference<'a, Table, Id, T> = ByIdRefernce<'a, Id, All<Table, T>>;
pub type SelectById<Table, Id, DeletedAtColumn, T> =
    ById<Id, FilterExisting<All<Table, T>, DeletedAtColumn>>;
pub type SelectByName<Table, Name, DeletedAtColumn, T> =
    ByName<Name, FilterExisting<All<Table, T>, DeletedAtColumn>>;
pub type SelectByTemplateId<Table, TemplateId, DeletedAtColumn, T> =
    ByTemplateId<TemplateId, FilterExisting<All<Table, T>, DeletedAtColumn>>;
pub type SelectByDeploymentId<Table, DeploymentId, DeletedAtColumn, T> =
    ByDeploymentId<DeploymentId, FilterExisting<All<Table, T>, DeletedAtColumn>>;
pub type SelectByTemplateIdAndUsername<Table, TemplateId, Username, DeletedAtColumn, T> =
    ByUsername<Username, ByTemplateId<TemplateId, FilterExisting<All<Table, T>, DeletedAtColumn>>>;
pub type SelectByEmailId<Table, EmailId, T> = ById<EmailId, All<Table, T>>;
type UpdateDeletedAt<DeletedAtColumn> = Eq<DeletedAtColumn, now>;
pub type SoftDelete<L, DeletedAtColumn> = Update<L, UpdateDeletedAt<DeletedAtColumn>>;
pub type SoftDeleteById<Id, DeleteAtColumn, Table> = SoftDelete<ById<Id, Table>, DeleteAtColumn>;
pub type UpdateById<Id, DeletedAtColumn, Table, T> =
    Update<FilterExisting<ById<Id, Table>, DeletedAtColumn>, T>;
pub type HardUpdateById<Id, Table, T> = Update<ById<Id, Table>, T>;
pub type Create<Type, Table> = InsertStatement<Table, <Type as Insertable<Table>>::Values>;
pub type CreateOrReplace<Type, Table> =
    ReplaceStatement<Table, <Type as Insertable<Table>>::Values>;
pub type CreateOrIgnore<Type, Table> =
    InsertOrIgnoreStatement<Table, <Type as Insertable<Table>>::Values>;
pub type DeleteById<Id, Table> =
    Filter<DeleteStatement<Table, <Table as IntoUpdateTarget>::WhereClause>, Eq<Id, Uuid>>;

pub type ArcDatabaseConnection = Arc<Mutex<PooledConnection<ConnectionManager<MysqlConnection>>>>;
pub struct Database {
    websocket_manager_address: Addr<WebSocketManager>,
    connection_pool: Pool<ConnectionManager<MysqlConnection>>,
    shared_connection: ArcDatabaseConnection,
}

impl Actor for Database {
    type Context = actix::Context<Self>;
}

impl Database {
    pub fn try_new(database_url: &str, websocket_manager: &Addr<WebSocketManager>) -> Result<Self> {
        let manager = ConnectionManager::<MysqlConnection>::new(database_url);
        let connection_pool = Pool::builder()
            .build(manager)
            .map_err(|error| anyhow!("Failed to create database connection pool: {}", error))?;
        let mut connection = connection_pool
            .get()
            .map_err(|error| anyhow!("Failed to get database connection: {}", error))?;
        let shared_connection = connection_pool.get()?;

        run_migrations(&mut *connection)
            .map_err(|error| anyhow!("Failed to run database migrations: {}", error))?;

        Ok(Self {
            connection_pool,
            websocket_manager_address: websocket_manager.clone(),
            shared_connection: Arc::new(Mutex::new(shared_connection)),
        })
    }

    pub fn get_connection(&self) -> Result<PooledConnection<ConnectionManager<MysqlConnection>>> {
        Ok(self.connection_pool.get()?)
    }
    pub fn get_shared_connection(&self) -> Result<ArcDatabaseConnection> {
        Ok(self.shared_connection.clone())
    }
    pub fn pick_connection(&self, use_shared_connection: bool) -> Result<ArcDatabaseConnection> {
        match use_shared_connection {
            true => self.get_shared_connection(),
            false => Ok(Arc::new(Mutex::new(self.get_connection()?))),
        }
    }
}
