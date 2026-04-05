use anyhow::{Ok, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::{
    common::{HelperSource, Source},
    Formalize,
};

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Condition {
    #[serde(default, alias = "Name", alias = "NAME")]
    pub name: Option<String>,
    #[serde(default, alias = "Command", alias = "COMMAND")]
    pub command: Option<String>,
    #[serde(default, alias = "Interval", alias = "INTERVAL")]
    pub interval: Option<u32>,
    #[serde(
        default,
        rename = "source",
        alias = "Source",
        alias = "SOURCE",
        skip_serializing
    )]
    source_helper: Option<HelperSource>,
    #[serde(default, skip_deserializing)]
    pub source: Option<Source>,
    #[serde(alias = "Description", alias = "DESCRIPTION")]
    pub description: Option<String>,
    #[serde(alias = "Environment", alias = "ENVIRONMENT")]
    pub environment: Option<Vec<String>>,
}

impl Formalize for Condition {
    fn formalize(&mut self) -> Result<()> {
        if let Some(source_helper) = &self.source_helper {
            self.source = Some(source_helper.to_owned().into());
        }

        let has_command = self.command.is_some();
        let has_interval = self.interval.is_some();
        let has_source = self.source.is_some();

        if has_source && (has_command || has_interval) {
            return Err(anyhow::anyhow!(
                "Condition must have Command and Interval or Source defined, not both"
            ));
        } else if has_command && !has_interval {
            return Err(anyhow::anyhow!(
                "Condition has Command defined but is missing Interval"
            ));
        } else if !has_command && has_interval {
            return Err(anyhow::anyhow!(
                "Condition has Interval defined but is missing Command"
            ));
        }
        Ok(())
    }
}

pub type Conditions = HashMap<String, Condition>;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse_sdl;

    #[test]
    fn conditions_are_mapped_correctly() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30
                condition-2:
                    source: digital-library-package
        "#;
        let conditions = parse_sdl(sdl).unwrap().conditions;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(conditions);
        });
    }

    #[test]
    fn handles_metrics_with_conditions_correctly() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30
                    description: This is a description for condition 1
                condition-2:
                    source: digital-library-package
                    description: This is a description for condition 2
            metrics:
                metric-1:
                    type: MANUAL
                    artifact: true
                    max-score: 10
                metric-2:
                    type: CONDITIONAL
                    max-score: 10
                    condition:  condition-2
        "#;
        let conditions = parse_sdl(sdl).unwrap().conditions;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(conditions);
        });
    }

    #[test]
    #[should_panic(expected = "Condition \"condition-3\" not found under Scenario Conditions")]
    fn identifies_missing_condition() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30
                    description: This is a description for condition 1
                condition-2:
                    source: digital-library-package
                    description: This is a description for condition 2
            metrics:
                metric-1:
                    type: MANUAL
                    artifact: true
                    max-score: 10
                metric-2:
                    type: CONDITIONAL
                    max-score: 10
                    condition:  condition-3
        "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    fn command_condition_is_parsed() {
        let sdl = r#"
            command: executable/path.sh
            interval: 30       

        "#;
        let condition = serde_yaml::from_str::<Condition>(sdl).unwrap();
        insta::assert_debug_snapshot!(condition);
    }

    #[test]
    fn library_condition_is_parsed() {
        let sdl = r#"
            source: digital-library-package 

        "#;
        let condition = serde_yaml::from_str::<Condition>(sdl).unwrap();
        insta::assert_debug_snapshot!(condition);
    }
}
