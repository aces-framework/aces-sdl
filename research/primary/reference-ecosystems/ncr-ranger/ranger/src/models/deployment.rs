use crate::{
    constants::{MAX_DEPLOYMENT_NAME_LENGTH, NAIVEDATETIME_DEFAULT_VALUE},
    errors::RangerError,
    middleware::keycloak::KeycloakInfo,
    schema::{
        deployment_elements::{self},
        deployments,
    },
    services::database::{
        deployment::UpdateDeploymentElement, participant::GetParticipants, All, Create,
        CreateOrIgnore, Database, FilterExisting, SelectById, SoftDelete, SoftDeleteById,
        UpdateById,
    },
    utilities::{create_database_error_handler, create_mailbox_error_handler, Validation},
};
use actix::Addr;
use anyhow::{anyhow, Result};
use chrono::NaiveDateTime;
use diesel::{
    helper_types::{Eq, Filter},
    sql_types::Text,
    AsChangeset, AsExpression, ExpressionMethods, FromSqlRow, Identifiable, Insertable, QueryDsl,
    Queryable, Selectable, SelectableHelper,
};
use ranger_grpc::{capabilities::DeployerType as GrpcDeployerType, ExecutorResponse};
use serde::{Deserialize, Serialize};

use super::helpers::{deployer_type::DeployerType, uuid::Uuid};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NewDeploymentResource {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub deployment_group: String,
    pub group_name: Option<String>,
    pub sdl_schema: String,
    pub start: NaiveDateTime,
    pub end: NaiveDateTime,
}

#[derive(Clone, Debug, Deserialize, Serialize, Insertable)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = deployments)]
pub struct NewDeployment {
    pub id: Uuid,
    pub name: String,
    pub deployment_group: String,
    pub group_name: Option<String>,
    pub sdl_schema: String,
    pub exercise_id: Uuid,
    pub start: NaiveDateTime,
    pub end: NaiveDateTime,
}

impl NewDeployment {
    pub fn new(resource: NewDeploymentResource, exercise_id: Uuid) -> Self {
        Self {
            id: resource.id,
            name: resource.name,
            deployment_group: resource.deployment_group,
            group_name: resource.group_name,
            sdl_schema: resource.sdl_schema,
            exercise_id,
            start: resource.start,
            end: resource.end,
        }
    }

    pub fn create_insert(&self) -> Create<&Self, deployments::table> {
        diesel::insert_into(deployments::table).values(self)
    }
}

impl Validation for NewDeployment {
    fn validate(&self) -> Result<(), RangerError> {
        if self.name.len() > MAX_DEPLOYMENT_NAME_LENGTH {
            return Err(RangerError::DeploymentNameTooLong);
        }
        Ok(())
    }
}

#[derive(Queryable, Selectable, Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = deployments)]
pub struct Deployment {
    pub id: Uuid,
    pub name: String,
    pub deployment_group: String,
    pub sdl_schema: String,
    pub group_name: Option<String>,
    pub exercise_id: Uuid,
    pub start: NaiveDateTime,
    pub end: NaiveDateTime,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub deleted_at: NaiveDateTime,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ParticipantDeployment {
    pub id: Uuid,
    pub name: String,
    pub exercise_id: Uuid,
    pub start: NaiveDateTime,
    pub end: NaiveDateTime,
    pub updated_at: String,
}

impl From<Deployment> for ParticipantDeployment {
    fn from(deployment: Deployment) -> Self {
        Self {
            id: deployment.id,
            name: deployment.name,
            start: deployment.start,
            end: deployment.end,
            exercise_id: deployment.exercise_id,
            updated_at: deployment.updated_at.to_string(),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, FromSqlRow, AsExpression, Eq, Deserialize, Serialize)]
#[diesel(sql_type = Text)]
pub enum ElementStatus {
    Ongoing,
    Success,
    Failed,
    Removed,
    RemoveFailed,
    ConditionWarning,
    ConditionSuccess,
    ConditionPolling,
    ConditionClosed,
}

pub trait ScenarioReference
where
    Self: Send,
{
    fn reference(&self) -> String;
}

impl ScenarioReference for sdl_parser::common::Source {
    fn reference(&self) -> String {
        format!("{}-{}", self.name, self.version)
    }
}

impl ScenarioReference for String {
    fn reference(&self) -> String {
        self.clone()
    }
}

pub type BoxedScenarioReference = Box<dyn ScenarioReference>;

#[derive(
    Insertable,
    Identifiable,
    Queryable,
    Selectable,
    Clone,
    Debug,
    Deserialize,
    Serialize,
    AsChangeset,
)]
#[diesel(table_name = deployment_elements)]
#[serde(rename_all = "camelCase")]
pub struct DeploymentElement {
    pub id: Uuid,
    pub deployment_id: Uuid,
    pub scenario_reference: String,
    pub handler_reference: Option<String>,
    pub deployer_type: DeployerType,
    pub status: ElementStatus,
    pub executor_stdout: Option<String>,
    pub executor_stderr: Option<String>,
    pub event_id: Option<Uuid>,
    pub parent_node_id: Option<Uuid>,
    pub error_message: Option<String>,
}

type ByDeploymentId<T> = Filter<
    FilterExisting<T, deployment_elements::deleted_at>,
    Eq<deployment_elements::deployment_id, Uuid>,
>;

type ByDeploymentIdByScenarioReference<T> = Filter<
    ByDeploymentId<All<deployment_elements::table, T>>,
    Eq<deployment_elements::scenario_reference, String>,
>;

type ByDeploymentIdByHandlerReference<T> = Filter<
    ByDeploymentId<All<deployment_elements::table, T>>,
    Eq<deployment_elements::handler_reference, String>,
>;

type ByEventId<T> = Filter<
    FilterExisting<T, deployment_elements::deleted_at>,
    Eq<deployment_elements::event_id, Uuid>,
>;

type ByEventIdByParentNodeId<T> = Filter<
    ByEventId<All<deployment_elements::table, T>>,
    Eq<deployment_elements::parent_node_id, Uuid>,
>;

impl DeploymentElement {
    pub fn new_ongoing(
        deployment_id: Uuid,
        source_box: Box<dyn ScenarioReference>,
        deployer_type: GrpcDeployerType,
        event_id: Option<Uuid>,
        parent_node_id: Option<Uuid>,
    ) -> Self {
        Self {
            id: Uuid::random(),
            deployment_id,
            scenario_reference: source_box.reference(),
            deployer_type: DeployerType(deployer_type),
            status: ElementStatus::Ongoing,
            executor_stdout: None,
            executor_stderr: None,
            event_id,
            handler_reference: None,
            parent_node_id,
            error_message: None,
        }
    }

    pub fn new(
        deployment_id: Uuid,
        source_box: Box<dyn ScenarioReference>,
        handler_reference: Option<String>,
        deployer_type: GrpcDeployerType,
        status: ElementStatus,
    ) -> Self {
        Self {
            id: Uuid::random(),
            deployment_id,
            scenario_reference: source_box.reference(),
            handler_reference,
            deployer_type: DeployerType(deployer_type),
            status,
            executor_stdout: None,
            executor_stderr: None,
            event_id: None,
            parent_node_id: None,
            error_message: None,
        }
    }

    pub async fn update(
        &mut self,
        database_address: &Addr<Database>,
        exercise_id: Uuid,
        status: ElementStatus,
        handler_reference: Option<String>,
    ) -> Result<()> {
        self.status = status;
        self.handler_reference = handler_reference;

        database_address
            .send(UpdateDeploymentElement(exercise_id, self.clone(), true))
            .await??;
        Ok(())
    }

    pub fn set_stdout_and_stderr(&mut self, executor_response: &ExecutorResponse) {
        self.executor_stdout = match executor_response.stdout.is_empty() {
            true => None,
            false => Some(executor_response.stdout.clone()),
        };
        self.executor_stderr = match executor_response.stderr.is_empty() {
            true => None,
            false => Some(executor_response.stderr.clone()),
        };
    }

    fn all_with_deleted() -> All<deployment_elements::table, Self> {
        deployment_elements::table.select(DeploymentElement::as_select())
    }

    fn all(
    ) -> FilterExisting<All<deployment_elements::table, Self>, deployment_elements::deleted_at>
    {
        Self::all_with_deleted()
            .filter(deployment_elements::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(
        id: Uuid,
    ) -> SelectById<
        deployment_elements::table,
        deployment_elements::id,
        deployment_elements::deleted_at,
        Self,
    > {
        Self::all().filter(deployment_elements::id.eq(id))
    }

    pub fn by_deployment_id(
        deployment_id: Uuid,
    ) -> ByDeploymentId<All<deployment_elements::table, Self>> {
        Self::all().filter(deployment_elements::deployment_id.eq(deployment_id))
    }

    pub fn by_deployment_id_by_scenario_reference(
        deployment_id: Uuid,
        scenario_reference: String,
    ) -> ByDeploymentIdByScenarioReference<Self> {
        Self::all()
            .filter(deployment_elements::deployment_id.eq(deployment_id))
            .filter(deployment_elements::scenario_reference.eq(scenario_reference.reference()))
    }

    pub fn by_deployment_id_by_handler_reference(
        deployment_id: Uuid,
        handler_reference: String,
    ) -> ByDeploymentIdByHandlerReference<Self> {
        Self::all()
            .filter(deployment_elements::deployment_id.eq(deployment_id))
            .filter(deployment_elements::handler_reference.eq(handler_reference))
    }

    pub fn by_event_id(event_id: Uuid) -> ByEventId<All<deployment_elements::table, Self>> {
        Self::all().filter(deployment_elements::event_id.eq(event_id))
    }

    pub fn by_event_id_by_parent_node_id(
        event_id: Uuid,
        parent_node_id: Uuid,
    ) -> ByEventIdByParentNodeId<Self> {
        Self::all()
            .filter(deployment_elements::event_id.eq(event_id))
            .filter(deployment_elements::parent_node_id.eq(parent_node_id))
    }

    pub fn create_insert(&self) -> Create<&Self, deployment_elements::table> {
        diesel::insert_into(deployment_elements::table).values(self)
    }

    pub fn create_insert_or_ignore(&self) -> CreateOrIgnore<&Self, deployment_elements::table> {
        diesel::insert_or_ignore_into(deployment_elements::table).values(self)
    }

    pub fn create_update(
        &self,
    ) -> UpdateById<
        deployment_elements::id,
        deployment_elements::deleted_at,
        deployment_elements::table,
        &Self,
    > {
        diesel::update(deployment_elements::table)
            .filter(deployment_elements::id.eq(self.id))
            .filter(deployment_elements::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
            .set(self)
    }
}

impl Deployment {
    fn all_with_deleted() -> All<deployments::table, Self> {
        deployments::table.select(Deployment::as_select())
    }

    pub fn all() -> FilterExisting<All<deployments::table, Self>, deployments::deleted_at> {
        Self::all_with_deleted().filter(deployments::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(
        id: Uuid,
    ) -> SelectById<deployments::table, deployments::id, deployments::deleted_at, Self> {
        Self::all().filter(deployments::id.eq(id))
    }

    pub fn by_exercise_id(
        id: Uuid,
    ) -> SelectById<deployments::table, deployments::exercise_id, deployments::deleted_at, Self>
    {
        Self::all().filter(deployments::exercise_id.eq(id))
    }

    pub fn soft_delete_elements(
        &self,
    ) -> SoftDelete<ByDeploymentId<deployment_elements::table>, deployment_elements::deleted_at>
    {
        diesel::update(deployment_elements::table)
            .filter(deployment_elements::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
            .filter(deployment_elements::deployment_id.eq(self.id))
            .set(deployment_elements::deleted_at.eq(diesel::dsl::now))
    }

    pub fn soft_delete(
        &self,
    ) -> SoftDeleteById<deployments::id, deployments::deleted_at, deployments::table> {
        diesel::update(deployments::table.filter(deployments::id.eq(self.id)))
            .set(deployments::deleted_at.eq(diesel::dsl::now))
    }

    async fn is_member(
        &self,
        user_id: String,
        keycloak_info: KeycloakInfo,
        realm_name: String,
    ) -> Result<bool> {
        let role_name = self
            .group_name
            .clone()
            .ok_or_else(|| anyhow!("Exercise group name is not set"))?;
        let users = keycloak_info
            .service_user
            .realm_clients_with_id_roles_with_role_name_users_get(
                &realm_name,
                &keycloak_info.client_id,
                &role_name,
                None,
                None,
            )
            .await?;
        for user in users {
            if let Some(loop_user_id) = user.id {
                if loop_user_id == user_id {
                    return Ok(true);
                }
            }
        }
        Ok(false)
    }

    async fn is_assigned_entity(
        &self,
        user_id: String,
        database_address: &Addr<Database>,
    ) -> Result<bool> {
        let participants = database_address
            .send(GetParticipants(self.id))
            .await
            .map_err(create_mailbox_error_handler("Database"))?
            .map_err(create_database_error_handler("Get participants"))?;

        for participant in participants {
            if participant.user_id == user_id {
                return Ok(true);
            }
        }

        Ok(false)
    }

    pub async fn is_connected(
        &self,
        user_id: String,
        database_address: &Addr<Database>,
        keycloak_info: KeycloakInfo,
        realm_name: String,
    ) -> Result<bool> {
        let is_member = self
            .is_member(user_id.clone(), keycloak_info, realm_name.clone())
            .await?;
        let is_connected = self
            .is_assigned_entity(user_id.clone(), database_address)
            .await?;

        Ok(is_member && is_connected)
    }
}
