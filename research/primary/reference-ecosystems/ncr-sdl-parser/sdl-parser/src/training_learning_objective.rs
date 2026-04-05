use std::collections::HashMap;

use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};

use crate::{evaluation::Evaluation, helpers::Connection};

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct TrainingLearningObjective {
    #[serde(alias = "Name", alias = "NAME")]
    pub name: Option<String>,
    #[serde(alias = "Description", alias = "DESCRIPTION")]
    pub description: Option<String>,
    #[serde(alias = "Evaluation", alias = "EVALUATION")]
    pub evaluation: String,
}

pub type TrainingLearningObjectives = HashMap<String, TrainingLearningObjective>;

impl Connection<Evaluation> for (&String, &TrainingLearningObjective) {
    fn validate_connections(&self, potential_evaluation_names: &Option<Vec<String>>) -> Result<()> {
        if let Some(existing_evaluation_names) = potential_evaluation_names {
            if !existing_evaluation_names.contains(&self.1.evaluation) {
                return Err(anyhow!(
                    "TLO \"{tlo_name}\" Evaluation \"{evaluation_name}\" not found under Scenario Evaluations",
                    tlo_name = self.0,
                    evaluation_name =self.1.evaluation
                ));
            }
        } else {
            return Err(anyhow!(
                "TLO \"{tlo_name}\" requires an Evaluation but none found under Scenario",
                tlo_name = self.0
            ));
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse_sdl;

    #[test]
    fn parses_sdl_with_tlos() {
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
            vulnerabilities:
                vulnerability-1:
                    name: Some other vulnerability
                    description: some-description
                    technical: false
                    class: CWE-1343
                vulnerability-2:
                    name: Some vulnerability
                    description: some-description
                    technical: false
                    class: CWE-1341
            evaluations:
                evaluation-1:
                    description: some description
                    metrics:
                        - metric-1
                        - metric-2
                    min-score: 50
            tlos:
                tlo-1:
                    description: some description
                    evaluation: evaluation-1
        "#;
        let tlos = parse_sdl(sdl).unwrap().tlos;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(tlos);
        });
    }

    #[test]
    fn parses_training_learning_objective() {
        let tlo_string = r#"
          name: test-training-learning-objective
          description: some description
          evaluation: evaluation-2
        "#;
        serde_yaml::from_str::<TrainingLearningObjective>(tlo_string).unwrap();
    }
}
