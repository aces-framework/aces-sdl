use super::helpers::uuid::Uuid;
use crate::models::ConditionMessage;
use bigdecimal::BigDecimal;
use chrono::NaiveDateTime;
use sdl_parser::metric::Metric;
use serde::{Deserialize, Serialize};

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Score {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub exercise_id: Uuid,
    pub deployment_id: Uuid,
    pub metric_name: Option<String>,
    pub metric_key: String,
    pub vm_name: String,
    pub value: BigDecimal,
    pub timestamp: NaiveDateTime,
}

impl Score {
    pub fn new(
        exercise_id: Uuid,
        deployment_id: Uuid,
        metric_name: Option<String>,
        metric_key: String,
        vm_name: String,
        value: BigDecimal,
        timestamp: NaiveDateTime,
    ) -> Self {
        Self {
            id: Uuid::random(),
            exercise_id,
            deployment_id,
            metric_name,
            metric_key,
            vm_name,
            value,
            timestamp,
        }
    }

    pub fn from_conditionmessage_and_metric(
        condition_message: ConditionMessage,
        sdl_metric: (String, Metric),
        vm_name: String,
    ) -> Self {
        Self {
            id: condition_message.id,
            exercise_id: condition_message.exercise_id,
            deployment_id: condition_message.deployment_id,
            metric_name: sdl_metric.1.name,
            metric_key: sdl_metric.0,
            vm_name,
            value: condition_message.value * BigDecimal::from(sdl_metric.1.max_score),
            timestamp: condition_message.created_at,
        }
    }
}

impl From<super::Metric> for Score {
    fn from(metric: super::Metric) -> Self {
        let score: BigDecimal = match metric.score {
            Some(score) => BigDecimal::from(score),
            None => BigDecimal::from(0),
        };

        Score::new(
            metric.exercise_id,
            metric.deployment_id,
            metric.name,
            metric.sdl_key,
            metric.entity_selector,
            score,
            metric.updated_at,
        )
    }
}
