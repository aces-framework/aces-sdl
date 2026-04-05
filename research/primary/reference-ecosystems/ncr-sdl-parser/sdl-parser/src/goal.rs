use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::{
    helpers::Connection, training_learning_objective::TrainingLearningObjective, Formalize,
};

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Goal {
    #[serde(alias = "Name", alias = "NAME")]
    pub name: Option<String>,
    #[serde(alias = "Description", alias = "DESCRIPTION")]
    pub description: Option<String>,
    #[serde(alias = "Tlos", alias = "TLOS")]
    pub tlos: Vec<String>,
}

pub type Goals = HashMap<String, Goal>;

impl Formalize for Goal {
    fn formalize(&mut self) -> Result<()> {
        if self.tlos.is_empty() {
            return Err(anyhow::anyhow!("Goal requires at least one TLO"));
        }
        Ok(())
    }
}

impl Connection<TrainingLearningObjective> for (&String, &Goal) {
    fn validate_connections(&self, potential_tlo_names: &Option<Vec<String>>) -> Result<()> {
        let tlos = &self.1.tlos;

        if let Some(tlo_names) = potential_tlo_names {
            for tlo_name in tlos {
                if !tlo_names.contains(tlo_name) {
                    return Err(anyhow!("TLO \"{tlo_name}\" not found under Scenario TLOs"));
                }
            }
        } else {
            return Err(anyhow!(
                "Goal requires at least one TLO but none found under Scenario"
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
    fn parses_sdl_with_goals() {
        let sdl = r#"
          name: test-scenario
          description: some-description
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
          goals:
            goal-1:
                description: "new goal"
                tlos: 
                  - tlo-1                   
      "#;
        let goals = parse_sdl(sdl).unwrap().goals;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(goals);
        });
    }

    #[test]
    #[should_panic(expected = "Goal requires at least one TLO but none found under Scenario")]
    fn fails_without_tlos() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            goals:
                goal-1:
                    description: "new goal"
                    tlos: 
                        - tlo-1                   
      "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    fn parses_single_goal() {
        let goal_yml = r#"
          description: "new goal"
          tlos: 
            - tlo-1
            - tlo-2
            - tlo-3
        "#;
        serde_yaml::from_str::<Goal>(goal_yml).unwrap();
    }

    #[test]
    #[should_panic(expected = "Goal requires at least one TLO")]
    fn fails_with_empty_tlo_list() {
        let goal_yml = r#"
          description: "new goal"
          tlos:
        "#;
        serde_yaml::from_str::<Goal>(goal_yml)
            .unwrap()
            .formalize()
            .unwrap();
    }
}
