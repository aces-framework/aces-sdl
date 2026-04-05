use std::collections::HashMap;

use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};

use crate::{
    event::Event, helpers::Connection, training_learning_objective::TrainingLearningObjective,
    vulnerability::Vulnerability,
};

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub enum ExerciseRole {
    White,
    Green,
    Red,
    Blue,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Entity {
    #[serde(alias = "Name", alias = "NAME")]
    pub name: Option<String>,
    #[serde(alias = "Description", alias = "DESCRIPTION")]
    pub description: Option<String>,
    #[serde(alias = "Role", alias = "ROLE")]
    pub role: Option<ExerciseRole>,
    #[serde(alias = "Mission", alias = "MISSION")]
    pub mission: Option<String>,
    #[serde(alias = "Categories", alias = "CATEGORIES")]
    pub categories: Option<Vec<String>>,
    #[serde(alias = "Vulnerabilities", alias = "VULNERABILITIES")]
    pub vulnerabilities: Option<Vec<String>>,
    #[serde(alias = "TLOs", alias = "TLOS")]
    pub tlos: Option<Vec<String>>,
    #[serde(alias = "Events", alias = "EVENTS")]
    pub events: Option<Vec<String>>,
    #[serde(alias = "Entities", alias = "ENTITIES")]
    pub entities: Option<Entities>,
}

impl Connection<TrainingLearningObjective> for (&String, &Entity) {
    fn validate_connections(&self, potential_tlo_names: &Option<Vec<String>>) -> Result<()> {
        let tlos = &self.1.tlos;

        if let Some(tlos) = tlos {
            if let Some(tlo_names) = potential_tlo_names {
                for tlo_name in tlos {
                    if !tlo_names.contains(tlo_name) {
                        return Err(anyhow!(
                            "Entity \"{entity_name}\" TLO \"{tlo_name}\" not found under Scenario TLOs",
                            entity_name = self.0
                        ));
                    }
                }
            } else {
                return Err(anyhow!(
                    "Entity \"{entity_name}\" has TLOs but none found under Scenario",
                    entity_name = self.0
                ));
            }
        }

        Ok(())
    }
}

impl Connection<Vulnerability> for (&String, &Entity) {
    fn validate_connections(
        &self,
        potential_vulnerability_names: &Option<Vec<String>>,
    ) -> Result<()> {
        let vulnerabilities = &self.1.vulnerabilities;

        if let Some(vulnerabilities) = vulnerabilities {
            if let Some(vulnerability_names) = potential_vulnerability_names {
                for vulnerability_name in vulnerabilities {
                    if !vulnerability_names.contains(vulnerability_name) {
                        return Err(anyhow!(
                            "Entity \"{entity_name}\" Vulnerability \"{vulnerability_name}\" not found under Scenario Vulnerabilities",
                            entity_name = self.0
                        ));
                    }
                }
            } else {
                return Err(anyhow!(
                    "Entity \"{entity_name}\" has Vulnerabilities but none found under Scenario",
                    entity_name = self.0
                ));
            }
        }

        Ok(())
    }
}

impl Connection<Event> for (&String, &Entity) {
    fn validate_connections(&self, potential_event_names: &Option<Vec<String>>) -> Result<()> {
        let entity_events = &self.1.events;

        if let Some(entity_events) = entity_events {
            if let Some(sdl_event_names) = potential_event_names {
                for entity_event_name in entity_events {
                    if !sdl_event_names.contains(entity_event_name) {
                        return Err(anyhow!(
                            "Entity \"{entity_name}\" Event \"{entity_event_name}\" not found under Scenario Events",
                            entity_name = self.0
                        ));
                    }
                }
            } else {
                return Err(anyhow!(
                    "Entity \"{entity_name}\" has Events but none found under Scenario",
                    entity_name = self.0
                ));
            }
        }

        Ok(())
    }
}

pub type Entities = HashMap<String, Entity>;
pub trait Flatten {
    fn flatten(&self) -> Self;
}

impl Flatten for Entities {
    fn flatten(&self) -> Self {
        let mut result = self.clone();

        self.iter().for_each(|(key, entity)| {
            if let Some(child_entities) = &entity.entities {
                Self::flatten(child_entities)
                    .into_iter()
                    .for_each(|(child_key, child_entity)| {
                        result.insert(format!("{key}.{child_key}"), child_entity);
                    })
            }
        });

        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse_sdl;

    #[test]
    fn parses_sdl_with_entities() {
        let sdl = r#"
          name: test-scenario
          description: some-description
          stories:
            story-1:
                speed: 1
                scripts:
                    - script-1
          scripts:
            script-1:
                start-time: 0
                end-time: 3 hour 30 min
                speed: 1
                events:
                    earthquake: 1 hour
          events:
            earthquake:
                description: "Here comes another earthquake"
                source: earthquake-package
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
          entities:
              my-organization:
                  name: "My Organization"
                  description: "This is my organization"
                  role: White
                  mission: "defend"
                  events:
                    - earthquake
                  categories:
                    - Foundation
                    - Organization
                  vulnerabilities:
                    - vulnerability-2
                  tlos:
                    - tlo-1
                  entities:
                    fish:
                        name: "Shark"
                        description: "This is my organization"
                        mission: "swim around"
                        categories:
                            - Animal
      "#;
        let entities = parse_sdl(sdl).unwrap().entities;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(entities);
        });
    }

    #[test]
    fn parses_single_entity() {
        let entity_yml = r#"
          name: "My Organization"
          description: "This is my organization"
          role: White
          mission: "defend"
          categories:
            - Foundation
            - Organization
          vulnerabilities:
            - vulnerability-2
          tlos:
            - tlo-1
            - tlo-2
        "#;
        serde_yaml::from_str::<Entity>(entity_yml).unwrap();
    }

    #[test]
    fn parses_nested_entity() {
        let entity_yml = r#"
          name: "My Organization"
          description: "This is my organization"
          role: White
          mission: "defend"
          categories:
            - Foundation
            - Organization
          vulnerabilities:
            - vulnerability-2
          tlos:
            - tlo-1
            - tlo-2
          entities:
            fish:
              name: "Shark"
              description: "This is my organization"
              mission: "swim around"
              categories:
                - Animal
        "#;
        serde_yaml::from_str::<Entity>(entity_yml).unwrap();
    }

    #[test]
    #[should_panic(
        expected = "Entity \"my-organization\" TLO \"tlo-2\" not found under Scenario TLOs"
    )]
    fn fails_parsing_entity_with_nonexisting_tlo() {
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
          entities:
              my-organization:
                  name: "My Organization"
                  description: "This is my organization"
                  role: White
                  mission: "defend"
                  categories:
                    - Foundation
                    - Organization
                  vulnerabilities:
                    - vulnerability-2
                  tlos:
                    - tlo-1
                    - tlo-2
                  entities:
                    fish:
                        name: "Shark"
                        description: "This is my organization"
                        mission: "swim around"
                        categories:
                            - Animal
      "#;
        let entities = parse_sdl(sdl).unwrap().entities;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(entities);
        });
    }

    #[test]
    #[should_panic(
        expected = "Entity \"my-organization.fish\" TLO \"tlo-i-don't-exist\" not found under Scenario TLOs"
    )]
    fn fails_parsing_child_entity_with_nonexisting_tlo() {
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
          entities:
              my-organization:
                  name: "My Organization"
                  description: "This is my organization"
                  role: White
                  mission: "defend"
                  categories:
                    - Foundation
                    - Organization
                  vulnerabilities:
                    - vulnerability-2
                  tlos:
                    - tlo-1
                  entities:
                    fish:
                        name: "Shark"
                        description: "This is my organization"
                        mission: "swim around"
                        categories:
                            - Animal
                        tlos:
                            - tlo-i-don't-exist
      "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(
        expected = "Entity \"my-organization.fish\" Vulnerability \"vulnerability-i-don't-exist\" not found under Scenario Vulnerabilities"
    )]
    fn fails_parsing_child_entity_with_nonexisting_vulnerability() {
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
          entities:
              my-organization:
                  name: "My Organization"
                  description: "This is my organization"
                  role: White
                  mission: "defend"
                  categories:
                    - Foundation
                    - Organization
                  vulnerabilities:
                    - vulnerability-2
                  tlos:
                    - tlo-1
                  entities:
                    fish:
                        name: "Shark"
                        description: "This is my organization"
                        mission: "swim around"
                        categories:
                            - Animal
                        vulnerabilities:
                            - vulnerability-i-don't-exist
      "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    fn parses_entity_with_events() {
        let sdl = r#"
          name: test-scenario
          events:
            my-cool-event:
                description: "This is my event"
            my-other-cool-event:
                description: "This is my other event"
          entities:
            blue-team:
                role: Blue
                events:
                    - my-cool-event
                entities:
                    blue-player:
                        role: Blue
                        events:
                            -  my-other-cool-event
      "#;
        let entities = parse_sdl(sdl).unwrap().entities;
        insta::assert_yaml_snapshot!(entities);
    }

    #[test]
    #[should_panic(
        expected = "Entity \"blue-team\" Event \"i-don't-exist\" not found under Scenario Events"
    )]
    fn fails_parsing_entity_with_nonexisting_event() {
        let sdl = r#"
          name: test-scenario
          events:
            my-cool-event:
                description: "This is my event"
          entities:
            blue-team:
                role: Blue
                events:
                - i-don't-exist
      "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(
        expected = "Entity \"blue-team.blue-player\" Event \"i-don't-exist\" not found under Scenario Events"
    )]
    fn fails_parsing_child_entity_with_nonexisting_event() {
        let sdl = r#"
          name: test-scenario
          events:
            my-cool-event:
                description: "This is my event"
          entities:
            blue-team:
                role: Blue
                entities:
                    blue-player:
                        role: Blue
                        events:
                            - i-don't-exist
      "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(expected = "Entity \"blue-team\" has Events but none found under Scenario")]
    fn fails_parsing_entity_with_no_events_defined() {
        let sdl = r#"
          name: test-scenario
          entities:
            blue-team:
                role: Blue
                events:
                - i-don't-exist
      "#;
        parse_sdl(sdl).unwrap();
    }
}
