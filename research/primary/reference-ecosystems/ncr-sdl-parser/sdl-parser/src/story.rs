use crate::helpers::Connection;
use crate::Formalize;
use crate::{constants::default_speed_value, script::Script};
use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(PartialEq, Debug, Serialize, Deserialize, Clone, Default)]
pub struct Story {
    #[serde(default, alias = "Name", alias = "NAME")]
    pub name: Option<String>,
    #[serde(default = "default_speed_value", alias = "Speed", alias = "SPEED")]
    pub speed: f64,
    #[serde(alias = "Scripts", alias = "SCRIPTS")]
    pub scripts: Vec<String>,
    #[serde(alias = "Description", alias = "DESCRIPTION")]
    pub description: Option<String>,
}

impl Story {
    pub fn new(potential_speed: Option<f64>) -> Self {
        Self {
            speed: match potential_speed {
                Some(speed) => speed,
                None => default_speed_value(),
            },
            ..Default::default()
        }
    }
}

pub type Stories = HashMap<String, Story>;

impl Formalize for Story {
    fn formalize(&mut self) -> Result<()> {
        if self.scripts.is_empty() {
            return Err(anyhow!("Story must have have at least one Script"));
        }

        if self.speed < 1.0 {
            return Err(anyhow!("Story speed value must be at least 1.0"));
        }

        Ok(())
    }
}

impl Connection<Script> for (&String, &Story) {
    fn validate_connections(&self, potential_script_names: &Option<Vec<String>>) -> Result<()> {
        if potential_script_names.is_none() {
            return Err(anyhow!(
                "Story \"{story_name}\" requires at least one Script but none found under Scenario",
                story_name = self.0
            ));
        };

        if let Some(script_names) = potential_script_names {
            for script_name in &self.1.scripts {
                if !script_names.contains(script_name) {
                    return Err(anyhow!("Script \"{script_name}\" not found under Scenario"));
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
    fn parses_sdl_with_stories() {
        let sdl = r#"
                name: test-scenario
                description: some description
                stories: 
                    story-1: 
                        speed: 1
                        scripts: 
                            - my-cool-script
                conditions:
                    condition-1:
                        command: executable/path.sh
                        interval: 30
                scripts:
                    my-cool-script:
                        start-time: 10min 2 sec
                        end-time: 1 week 1day 1h 10 ms
                        speed: 1.5
                        events:
                            my-cool-event: 20 min
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
        let schema = parse_sdl(sdl).unwrap();

        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(schema);
        });
    }

    #[test]
    fn parses_single_story() {
        let story = r#" 
            speed: 1
            scripts: 
                - script-1
                - script-2
     
      "#;
        serde_yaml::from_str::<Story>(story).unwrap();
    }

    #[test]
    #[should_panic(expected = "Story speed value must be at least 1.0")]
    fn fails_speed_is_zero() {
        let story = r#"
            speed: 0
            scripts: 
                - script-1
                - script-2
      "#;
        serde_yaml::from_str::<Story>(story)
            .unwrap()
            .formalize()
            .unwrap();
    }

    #[test]
    fn adds_default_speed() {
        let story = r#"
            scripts: 
                - script-1
                - script-2
      "#;

        let story = serde_yaml::from_str::<Story>(story).unwrap();

        assert_eq!(story.speed, 1.0);
    }

    #[test]
    #[should_panic(expected = "Story must have have at least one Script")]
    fn fails_when_scripts_is_empty() {
        let story = r#"
            speed: 1
            scripts:
      "#;
        serde_yaml::from_str::<Story>(story)
            .unwrap()
            .formalize()
            .unwrap();
    }

    #[test]
    #[should_panic(expected = "Error(\"missing field `scripts`\", line: 2, column: 13)")]
    fn fails_when_no_scripts_field() {
        let story = r#"
            speed: 15
      "#;
        serde_yaml::from_str::<Story>(story)
            .unwrap()
            .formalize()
            .unwrap();
    }

    #[test]
    #[should_panic(
        expected = "Story \"story-1\" requires at least one Script but none found under Scenario"
    )]
    fn fails_on_script_not_defined_for_story() {
        let sdl = r#"
                name: test-scenario
                description: some description
                stories: 
                    story-1: 
                        speed: 1
                        scripts: 
                            - script-1
            "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(expected = "Script \"script-1\" not found under Scenario")]
    fn fails_on_missing_script_for_story() {
        let sdl = r#"
                name: test-scenario
                description: some description
                stories: 
                    story-1: 
                        speed: 1
                        scripts: 
                            - script-1
                conditions:
                    condition-1:
                        command: executable/path.sh
                        interval: 30
                scripts:
                    my-cool-script:
                        start-time: 10min 2 sec
                        end-time: 1 week 1day 1h 10 ms
                        speed: 1.5
                        events:
                            my-cool-event: 20 min
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
}
