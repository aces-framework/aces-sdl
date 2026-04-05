use anyhow::{anyhow, Result};
use duration_str::parse;
use serde::{Deserialize, Deserializer, Serialize};
use std::collections::HashMap;

use crate::{event::Event, helpers::Connection, Formalize};

#[derive(PartialEq, Debug, Serialize, Deserialize, Clone)]
pub struct Script {
    #[serde(default, alias = "Name", alias = "NAME")]
    pub name: Option<String>,
    #[serde(
        deserialize_with = "deserialize_string_to_u64",
        rename = "start-time",
        alias = "Start-time",
        alias = "START-TIME"
    )]
    pub start_time: u64,
    #[serde(
        deserialize_with = "deserialize_string_to_u64",
        rename = "end-time",
        alias = "End-time",
        alias = "END-TIME"
    )]
    pub end_time: u64,
    #[serde(alias = "Speed", alias = "SPEED")]
    pub speed: f32,
    #[serde(
        deserialize_with = "deserialize_events",
        alias = "Events",
        alias = "EVENTS"
    )]
    pub events: HashMap<String, u64>,
    #[serde(alias = "Description", alias = "DESCRIPTION")]
    pub description: Option<String>,
}

pub type Scripts = HashMap<String, Script>;

impl Formalize for Script {
    fn formalize(&mut self) -> Result<()> {
        if self.events.is_empty() {
            return Err(anyhow!("Script must have have at least one Event"));
        } else if self.start_time > self.end_time {
            return Err(anyhow!("Scripts end-time must be greater than start-time"));
        }

        for event in self.events.values() {
            if *event < self.start_time {
                return Err(anyhow!(
                    "Event time must be greater than or equal to script start time"
                ));
            } else if *event > self.end_time {
                return Err(anyhow!(
                    "Event time must be less than or equal to script end time"
                ));
            }
        }

        if self.speed.is_sign_negative() {
            return Err(anyhow!("Scripts speed must have a positive value"));
        }

        Ok(())
    }
}

impl Connection<Event> for (&String, &Script) {
    fn validate_connections(&self, potential_event_names: &Option<Vec<String>>) -> Result<()> {
        if potential_event_names.is_none() {
            return Err(anyhow!(
                "Script \"{script_name}\" requires at least one Event but none found under Scenario",
                script_name = self.0
            ));
        };

        if let Some(event_names) = potential_event_names {
            for event_name in self.1.events.keys() {
                if !event_names.contains(event_name) {
                    return Err(anyhow!(
                        "Event \"{event_name}\" not found under Scenario Events"
                    ));
                }
            }
        }

        Ok(())
    }
}

fn parse_time_string_to_u64_sec(mut string: String) -> Result<u64> {
    if string.eq("0") {
        string = String::from("0sec");
    }

    string.retain(|char| !char.is_whitespace() && char != '_');

    let duration = parse(&string)?;
    Ok(duration.as_secs())
}

fn deserialize_string_to_u64<'de, D>(deserializer: D) -> Result<u64, D::Error>
where
    D: Deserializer<'de>,
{
    let string = String::deserialize(deserializer)?;
    let duration = parse_time_string_to_u64_sec(string)
        .map_err(|_| serde::de::Error::custom("failed to parse str to duration"))?;
    Ok(duration)
}

fn deserialize_events<'de, D>(deserializer: D) -> Result<HashMap<String, u64>, D::Error>
where
    D: Deserializer<'de>,
{
    let mut event_map: HashMap<String, String> = HashMap::deserialize(deserializer)?;

    let output = event_map
        .drain()
        .map(|(key, string)| {
            let duration = parse_time_string_to_u64_sec(string)
                .map_err(|_| serde::de::Error::custom("failed to parse str to duration"))?;
            Ok((key, duration))
        })
        .collect::<Result<HashMap<String, u64>, D::Error>>()?;

    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse_sdl;

    #[test]
    fn parses_sdl_with_scripts() {
        let sdl = r#"
            name: test-scenario
            description: some description
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
                        my-cool-event: 30 min
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
    fn parses_single_script() {
        let script = r#"
            start-time: 5h 10min 2sec
            end-time: 1 week 7d 3 hour 10 ms
            speed: 1
            events:
                my-cool-event: 6h 30min
      "#;
        serde_yaml::from_str::<Script>(script).unwrap();
    }

    #[test]
    #[should_panic(expected = "Scripts end-time must be greater than start-time")]
    fn fails_end_time_larger_than_start_time() {
        let script = r#"
            start-time: 1 year 5h 10min 2sec
            end-time: 1 week 7d 3 hour 10 ms
            speed: 1
            events:
                my-cool-event: 6h 30min
      "#;
        serde_yaml::from_str::<Script>(script)
            .unwrap()
            .formalize()
            .unwrap();
    }

    #[test]
    fn parses_zero_without_unit() {
        let script = r#"
            start-time: 0
            end-time: 1 week 7d 3 hour 10 ms
            speed: 1
            events:
                my-cool-event: 0
      "#;
        serde_yaml::from_str::<Script>(script)
            .unwrap()
            .formalize()
            .unwrap();
    }

    #[test]
    fn parses_underscore_formatted_numbers() {
        let script = r#"
            start-time: _1_0__0__ min
            end-time: 1_000_000s
            speed: 1
            events:
                my-cool-event: 1_2_0 min
      "#;

        let script = serde_yaml::from_str::<Script>(script).unwrap();

        assert_eq!(script.start_time, 6000);
        assert_eq!(script.end_time, 1000000);
        assert_eq!(script.events["my-cool-event"], 7200);
    }

    #[test]
    #[should_panic(expected = "Scripts speed must have a positive value")]
    fn fails_on_negative_speed_value() {
        let script = r#"
            start-time: 0
            end-time: 3 hour
            speed: -1.234
            events:
                my-cool-event: 2 hour
      "#;
        serde_yaml::from_str::<Script>(script)
            .unwrap()
            .formalize()
            .unwrap();
    }

    #[test]
    #[should_panic(
        expected = "Condition must have Command and Interval or Source defined, not both"
    )]
    fn fails_on_event_not_defined_for_script() {
        let sdl = r#"
                name: test-scenario
                description: some description
                conditions:
                    condition-1:
                        command: executable/path.sh
                        interval: 30
                        source: digital-library-package
                scripts:
                    my-cool-script:
                        start-time: 10min 2 sec
                        end-time: 1 week 1day 1h 10 ms
                        speed: 1.5
                        events:
                            my-cool-event: 20 min
            "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(expected = "Event \"my-cool-event\" not found under Scenario Events")]
    fn fails_on_missing_event_for_script() {
        let sdl = r#"
                name: test-scenario
                description: some description
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
                    my-embarrassing-event:
                        time: 0.2345678
                        conditions:
                            - condition-1
                        injects:
                            - my-cool-inject
            "#;
        parse_sdl(sdl).unwrap();
    }
}
