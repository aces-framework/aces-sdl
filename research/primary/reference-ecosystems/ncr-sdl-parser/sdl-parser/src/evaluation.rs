use std::collections::HashMap;

use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};

use crate::{helpers::Connection, metric::Metric, metric::Metrics, Formalize};

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct MinScore {
    pub absolute: Option<u32>,
    pub percentage: Option<u32>,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
#[serde(untagged)]
pub enum HelperScore {
    MinScore(MinScore),
    ShortMinScore(u32),
}

impl From<HelperScore> for MinScore {
    fn from(helper_source: HelperScore) -> Self {
        match helper_source {
            HelperScore::MinScore(score) => score,
            HelperScore::ShortMinScore(source) => MinScore {
                percentage: Some(source),
                absolute: None,
            },
        }
    }
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Evaluation {
    #[serde(default, alias = "Name", alias = "NAME")]
    pub name: Option<String>,
    #[serde(alias = "Description", alias = "DESCRIPTION")]
    pub description: Option<String>,
    #[serde(alias = "Metrics", alias = "METRICS")]
    pub metrics: Vec<String>,
    #[serde(
        default,
        rename = "min-score",
        alias = "Min-score",
        alias = "MIN-SCORE",
        skip_serializing
    )]
    pub _helper_min_score: Option<HelperScore>,
    #[serde(default, skip_deserializing)]
    pub min_score: Option<MinScore>,
}

impl Evaluation {
    pub fn validate_evaluation_metric_scores(
        &self,
        potential_metrics: Option<&Metrics>,
    ) -> Result<()> {
        if let Some(metrics) = potential_metrics {
            let metric_score_sum = metrics.iter().map(|s| s.1.max_score).sum();
            if let Some(min_score) = &self.min_score {
                if let Some(absolute_min_score) = min_score.absolute {
                    if absolute_min_score > metric_score_sum {
                        return Err(anyhow!(
                            "Sum of metric scores has to be smaller than the evaluation min-score"
                        ));
                    }
                }
            }
        } else {
            return Err(anyhow!(
                "Evaluation requires Metrics but none found under Scenario",
            ));
        }
        Ok(())
    }
}

impl Connection<Metric> for (&String, &Evaluation) {
    fn validate_connections(&self, potential_metric_names: &Option<Vec<String>>) -> Result<()> {
        if let Some(metric_names) = potential_metric_names {
            for metric_name in &self.1.metrics {
                if !metric_names.contains(metric_name) {
                    return Err(anyhow::anyhow!(
                        "Evaluation \"{evaluation_name}\" Metric \"{metric_name}\" not found under Scenario Metrics",
                        evaluation_name = self.0
                    ));
                }
            }
        } else {
            return Err(anyhow::anyhow!(
                "Evaluation \"{evaluation_name}\" requires Metrics but none found under Scenario",
                evaluation_name = self.0
            ));
        }
        Ok(())
    }
}

pub type Evaluations = HashMap<String, Evaluation>;

impl Formalize for Evaluation {
    fn formalize(&mut self) -> Result<()> {
        if let Some(helper_min_score) = &self._helper_min_score {
            self.min_score = Some(helper_min_score.to_owned().into());
        } else {
            return Err(anyhow!("An Evaluation is missing min-score"));
        }
        if let Some(score) = &self.min_score {
            if score.absolute.is_some() && score.percentage.is_some() {
                return Err(anyhow!(
                    "An Evaluations min-score can only have either Absolute or Percentage defined, not both"
                ));
            }
        }
        if self.metrics.is_empty() {
            return Err(anyhow!("An Evaluation must have at least one Metric"));
        }
        if let Some(min_score) = &self.min_score {
            if let Some(percentage) = min_score.percentage {
                if percentage > 100 {
                    return Err(anyhow!("Min score percentage can not be over 100%"));
                }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse_sdl;

    #[test]
    fn parses_sdl_with_evaluation() {
        let sdl = r#"
            name: test-scenario
            description: some description
            start: 2022-01-20T13:00:00Z
            end: 2022-01-20T23:00:00Z
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30
            metrics:
                metric-1:
                    type: MANUAL
                    artifact: true
                    max-score: 10
                metric-2:
                    type: CONDITIONAL
                    max-score: 10
                    condition: condition-1
            evaluations:
                evaluation-1:
                    description: some description
                    metrics:
                        - metric-1
                        - metric-2
                    min-score: 50
        "#;
        let evaluations = parse_sdl(sdl).unwrap().evaluations;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(evaluations);
        });
    }

    #[test]
    #[should_panic(
        expected = "Evaluation \"evaluation-1\" Metric \"metric-2\" not found under Scenario Metrics"
    )]
    fn fails_with_missing_metric() {
        let sdl = r#"
            name: test-scenario
            description: some description
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30
            metrics:
                metric-1:
                    type: MANUAL
                    artifact: true
                    max-score: 10
            evaluations:
                evaluation-1:
                    description: some description
                    metrics:
                        - metric-1
                        - metric-2
                    min-score: 50
        "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    fn parses_shorthand_evaluation() {
        let evaluation_string = r#"
          description: some-description
          metrics:
            - metric-1
            - metric-2
          min-score: 50
        "#;
        let mut evaluation: Evaluation = serde_yaml::from_str(evaluation_string).unwrap();
        assert!(evaluation.formalize().is_ok());
    }

    #[test]
    fn parses_longhand_evaluation() {
        let evaluation_string = r#"
        description: some-description
        metrics:
          - metric-1
          - metric-2
        min-score:
          absolute: 50
      "#;
        let mut evaluation: Evaluation = serde_yaml::from_str(evaluation_string).unwrap();
        assert!(evaluation.formalize().is_ok());
    }

    #[test]
    fn fails_to_parse_evaluation_with_both_scores() {
        let evaluation_string = r#"
          description: some-description
          metrics:
            - metric-1
            - metric-2
          min-score:
            absolute: 50
            percentage: 60
        "#;
        let mut evaluation: Evaluation = serde_yaml::from_str(evaluation_string).unwrap();
        assert!(evaluation.formalize().is_err());
    }

    #[test]
    #[should_panic(
        expected = "Sum of metric scores has to be smaller than the evaluation min-score"
    )]
    fn fails_to_parse_evaluation_too_small_min_score() {
        let sdl = r#"
            name: test-scenario
            description: some description
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30
            metrics:
                metric-1:
                    type: MANUAL
                    artifact: true
                    max-score: 10
                metric-2:
                    type: CONDITIONAL
                    max-score: 10
                    condition: condition-1
            evaluations:
                evaluation-1:
                    description: some description
                    metrics:
                        - metric-1
                        - metric-2
                    min-score:
                        absolute: 9999
        "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    fn fails_to_parse_too_high_min_score() {
        let evaluation_string = r#"
            description: some description
            metrics:
                - metric-1
                - metric-2
            min_score: 101
        "#;
        let mut evaluation: Evaluation = serde_yaml::from_str(evaluation_string).unwrap();
        assert!(evaluation.formalize().is_err());
    }
}
