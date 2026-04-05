use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::{
    common::{HelperSource, Source},
    condition::Condition,
    helpers::Connection,
    inject::Inject,
    Formalize,
};

#[derive(PartialEq, Debug, Serialize, Deserialize, Clone)]
pub struct Event {
    #[serde(default, alias = "Name", alias = "NAME")]
    pub name: Option<String>,
    #[serde(
        default,
        rename = "source",
        alias = "Source",
        alias = "SOURCE",
        skip_serializing
    )]
    _source_helper: Option<HelperSource>,
    #[serde(default, skip_deserializing)]
    pub source: Option<Source>,
    #[serde(alias = "Conditions", alias = "CONDITIONS")]
    pub conditions: Option<Vec<String>>,
    #[serde(alias = "Injects", alias = "INJECTS")]
    pub injects: Option<Vec<String>>,
    #[serde(alias = "Description", alias = "DESCRIPTION")]
    pub description: Option<String>,
}

pub type Events = HashMap<String, Event>;

impl Formalize for Event {
    fn formalize(&mut self) -> Result<()> {
        if self._source_helper.is_some() {
            if let Some(helper_source) = &self._source_helper {
                self.source = Some(helper_source.to_owned().into());
            } else {
                return Err(anyhow!("Event missing Source field"));
            }
        }

        Ok(())
    }
}
impl Connection<Condition> for (&String, &Event) {
    fn validate_connections(&self, potential_condition_names: &Option<Vec<String>>) -> Result<()> {
        if self.1.conditions.is_some() && potential_condition_names.is_none() {
            return Err(anyhow!(
                "Event \"{event_name}\" has Conditions but none found under Scenario",
                event_name = self.0
            ));
        }

        if let Some(required_conditions) = &self.1.conditions {
            if let Some(condition_names) = potential_condition_names {
                for event_condition_name in required_conditions {
                    if !condition_names.contains(event_condition_name) {
                        return Err(anyhow!(
                            "Condition \"{event_condition_name}\" not found under Scenario"
                        ));
                    }
                }
            }
        }

        Ok(())
    }
}

impl Connection<Inject> for (&String, &Event) {
    fn validate_connections(&self, potential_inject_names: &Option<Vec<String>>) -> Result<()> {
        if self.1.injects.is_some() && potential_inject_names.is_none() {
            return Err(anyhow!(
                "Event \"{event_name}\" has Injects but none found under Scenario",
                event_name = self.0
            ));
        }

        if let Some(required_injects) = &self.1.injects {
            if let Some(inject_names) = potential_inject_names {
                for event_inject_name in required_injects {
                    if !inject_names.contains(event_inject_name) {
                        return Err(anyhow!(
                            "Inject \"{event_inject_name}\" not found under Scenario",
                            event_inject_name = event_inject_name
                        ));
                    }
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
    fn parses_sdl_with_events() {
        let sdl = r#"
            name: test-scenario
            description: some description
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30
            injects:
                my-cool-inject:
                    source: inject-package
            events:
                my-cool-event:
                    source: event-package
                    conditions:
                        - condition-1
                    injects:
                        - my-cool-inject
        "#;
        let schema = parse_sdl(sdl).unwrap();

        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(schema);
        });
    }

    #[test]
    fn parses_single_event() {
        let event = r#"
            source: 
                name: event-package
                version: 1.0.0
            conditions:
                - condition-1
            injects:
                - my-cool-inject
      "#;
        serde_yaml::from_str::<Event>(event).unwrap();
    }

    #[test]
    #[should_panic(expected = "Condition \"condition-1\" not found under Scenario")]
    fn fails_on_missing_scenario_condition() {
        let sdl = r#"
                name: test-scenario
                description: some description
                conditions:
                    condition-3000:
                        source: digital-library-package
                injects:
                    my-cool-inject:
                        source: inject-package
                events:
                    my-cool-event:
                        conditions:
                            - condition-1
                        injects:
                            - my-cool-inject
            "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(
        expected = "Event \"my-cool-event\" has Conditions but none found under Scenario"
    )]
    fn fails_on_missing_conditions() {
        let sdl = r#"
                name: test-scenario
                description: some description
                injects:
                    my-cool-inject:
                        source: inject-package
                events:
                    my-cool-event:
                        conditions:
                            - condition-1
                        injects:
                            - my-cool-inject
            "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(expected = "Event \"my-cool-event\" has Injects but none found under Scenario")]
    fn fails_no_injects_under_scenario() {
        let sdl = r#"
                name: test-scenario
                description: some description
                events:
                    my-cool-event:
                        injects:
                            - my-cool-inject
            "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(expected = "Inject \"my-cool-inject\" not found under Scenario")]
    fn fails_on_missing_inject() {
        let sdl = r#"
                name: test-scenario
                description: some description
                conditions:
                    condition-1:
                        command: executable/path.sh
                        interval: 30
                injects:
                    inject-1:
                        source: inject-package
                events:
                    my-cool-event:
                        injects:
                            - my-cool-inject
            "#;
        parse_sdl(sdl).unwrap();
    }
}
