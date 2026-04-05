use super::helpers::uuid::Uuid;
use crate::{
    constants::NAIVEDATETIME_DEFAULT_VALUE,
    schema::metrics,
    services::database::{All, Create, FilterExisting, SelectById, SoftDeleteById, UpdateById},
};
use chrono::NaiveDateTime;
use diesel::{
    helper_types::{Eq, Filter},
    insert_into, AsChangeset, ExpressionMethods, Insertable, QueryDsl, Queryable, Selectable,
    SelectableHelper,
};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NewMetricResource {
    pub exercise_id: Uuid,
    pub deployment_id: Uuid,
    pub entity_selector: String,
    pub metric_key: String,
    pub role: String,
    pub text_submission: Option<String>,
}

#[derive(Insertable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = metrics)]
pub struct NewMetric {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub exercise_id: Uuid,
    pub deployment_id: Uuid,
    pub entity_selector: String,
    pub name: Option<String>,
    pub sdl_key: String,
    pub description: Option<String>,
    pub role: String,
    pub text_submission: Option<String>,
    pub max_score: u32,
}

impl NewMetric {
    pub fn new(
        name: Option<String>,
        description: Option<String>,
        max_score: u32,
        new_metric_resource: NewMetricResource,
    ) -> Self {
        Self {
            id: Uuid::random(),
            exercise_id: new_metric_resource.exercise_id,
            deployment_id: new_metric_resource.deployment_id,
            entity_selector: new_metric_resource.entity_selector,
            name,
            sdl_key: new_metric_resource.metric_key,
            description,
            role: new_metric_resource.role,
            text_submission: new_metric_resource.text_submission,
            max_score,
        }
    }

    pub fn create_insert(&self) -> Create<&Self, metrics::table> {
        insert_into(metrics::table).values(self)
    }
}

#[derive(Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = metrics)]
pub struct Metric {
    pub id: Uuid,
    pub exercise_id: Uuid,
    pub deployment_id: Uuid,
    pub entity_selector: String,
    pub name: Option<String>,
    pub sdl_key: String,
    pub description: Option<String>,
    pub role: String,
    pub text_submission: Option<String>,
    pub score: Option<u32>,
    pub max_score: u32,
    pub has_artifact: bool,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
    pub deleted_at: NaiveDateTime,
}

#[derive(AsChangeset, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = metrics)]
pub struct UpdateMetric {
    pub text_submission: Option<String>,
    pub score: Option<u32>,
}

impl UpdateMetric {
    pub fn create_update(
        &self,
        id: Uuid,
    ) -> UpdateById<metrics::id, metrics::deleted_at, metrics::table, &Self> {
        diesel::update(metrics::table)
            .filter(metrics::id.eq(id))
            .filter(metrics::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
            .set(self)
    }
}

pub type Metrics = Vec<Metric>;

type ByExerciseId<T> =
    Filter<FilterExisting<T, metrics::deleted_at>, Eq<metrics::exercise_id, Uuid>>;

type ByDeploymentId<T> =
    Filter<FilterExisting<T, metrics::deleted_at>, Eq<metrics::deployment_id, Uuid>>;

impl Metric {
    fn all_with_deleted() -> All<metrics::table, Self> {
        metrics::table.select(Self::as_select())
    }

    pub fn all() -> FilterExisting<All<metrics::table, Self>, metrics::deleted_at> {
        Self::all_with_deleted().filter(metrics::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(id: Uuid) -> SelectById<metrics::table, metrics::id, metrics::deleted_at, Self> {
        Self::all().filter(metrics::id.eq(id))
    }

    pub fn by_deployment_id(deployment_id: Uuid) -> ByDeploymentId<All<metrics::table, Self>> {
        Self::all().filter(metrics::deployment_id.eq(deployment_id))
    }

    pub fn by_exercise_id(exercise_id: Uuid) -> ByExerciseId<All<metrics::table, Self>> {
        Self::all().filter(metrics::exercise_id.eq(exercise_id))
    }

    pub fn soft_delete(&self) -> SoftDeleteById<metrics::id, metrics::deleted_at, metrics::table> {
        diesel::update(metrics::table.filter(metrics::id.eq(self.id)))
            .set(metrics::deleted_at.eq(diesel::dsl::now))
    }
}
