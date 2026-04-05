use crate::{
    common::{HelperSource, Source},
    helpers::Connection,
    vulnerability::Vulnerability,
    Formalize,
};
use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub enum FeatureType {
    #[serde(alias = "service", alias = "SERVICE")]
    Service,
    #[serde(alias = "configuration", alias = "CONFIGURATION")]
    Configuration,
    #[serde(alias = "artifact", alias = "ARTIFACT")]
    Artifact,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Feature {
    #[serde(alias = "Name", alias = "NAME")]
    pub name: Option<String>,
    #[serde(rename = "type", alias = "Type", alias = "TYPE")]
    pub feature_type: FeatureType,
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
    #[serde(default, alias = "Dependencies", alias = "DEPENDENCIES")]
    pub dependencies: Option<Vec<String>>,
    #[serde(default, alias = "Vulnerabilities", alias = "VULNERABILITIES")]
    pub vulnerabilities: Option<Vec<String>>,
    #[serde(default, alias = "Destination", alias = "DESTINATION")]
    pub destination: Option<String>,
    #[serde(alias = "Description", alias = "DESCRIPTION")]
    pub description: Option<String>,
    #[serde(alias = "Environment", alias = "ENVIRONMENT")]
    pub environment: Option<Vec<String>>,
}

impl Connection<Vulnerability> for (&String, &Feature) {
    fn validate_connections(
        &self,
        potential_vulnerability_names: &Option<Vec<String>>,
    ) -> Result<()> {
        if let Some(feature_vulnerabilities) = &self.1.vulnerabilities {
            if let Some(vulnerabilities) = potential_vulnerability_names {
                for vulnerability_name in feature_vulnerabilities.iter() {
                    if !vulnerabilities.contains(vulnerability_name) {
                        return Err(anyhow!(
                            "Feature \"{feature_name}\" Vulnerability \"{vulnerability_name}\" not found under Scenario Vulnerabilities",
                            feature_name = self.0
                        ));
                    }
                }
            } else {
                return Err(anyhow!(
                    "Feature \"{feature_name}\" has Vulnerabilities but none found under Scenario",
                    feature_name = self.0
                ));
            }
        }
        Ok(())
    }
}

pub type Features = HashMap<String, Feature>;

impl Formalize for Feature {
    fn formalize(&mut self) -> Result<()> {
        if let Some(helper_source) = &self._source_helper {
            self.source = Some(helper_source.to_owned().into());
        } else {
            return Err(anyhow!("Feature missing Source field"));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse_sdl;

    #[test]
    fn feature_source_fields_are_mapped_correctly() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            features:
                my-cool-feature:
                    type: Service
                    source: some-service
                my-cool-feature-config:
                    type: Configuration
                    source:
                        name: cool-config
                        version: 1.0.0
        "#;
        let features = parse_sdl(sdl).unwrap().features;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(features);
        });
    }

    #[test]
    fn feature_source_longhand_is_parsed() {
        let longhand_source = r#"
            type: artifact
            source:
                name: artifact-name
                version: 1.2.3
        "#;
        let feature = serde_yaml::from_str::<Feature>(longhand_source).unwrap();
        insta::assert_debug_snapshot!(feature);
    }
    #[test]
    fn feature_source_shorthand_is_parsed() {
        let shorthand_source = r#"
            type: artifact
            source: artifact-name
        "#;
        let feature = serde_yaml::from_str::<Feature>(shorthand_source).unwrap();
        insta::assert_debug_snapshot!(feature);
    }

    #[test]
    fn feature_includes_dependencies() {
        let feature_sdl = r#"
            type: Service
            source: some-service
            dependencies:
                - some-virtual-machine
                - some-switch
                - something-else
        "#;
        let feature = serde_yaml::from_str::<Feature>(feature_sdl).unwrap();
        insta::assert_debug_snapshot!(feature);
    }

    #[test]
    fn cyclic_feature_dependency_is_detected() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            features:
                my-cool-feature:
                    type: Service
                    source: some-service
                    dependencies: 
                        - my-less-cool-feature
                my-less-cool-feature:
                    type: Configuration
                    source:
                        name: cool-config
                        version: 1.0.0
                    dependencies: 
                        - my-cool-feature
        "#;
        let features = parse_sdl(sdl);
        assert!(features.is_err());
        assert_eq!(
            features.err().unwrap().to_string(),
            "Cyclic dependency detected"
        );
    }

    #[test]
    fn feature_cyclic_self_dependency_is_detected() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            features:
                my-cool-feature:
                    type: Service
                    source: some-service
                    dependencies: 
                        - my-cool-feature
        "#;
        let features = parse_sdl(sdl);
        assert!(features.is_err());
        assert_eq!(
            features.err().unwrap().to_string(),
            "Cyclic dependency detected"
        );
    }

    #[test]
    fn can_parse_destination_environment() {
        let feature = r#"
                    type: Service
                    source: some-service
                    dependencies: 
                        - my-cool-feature
                    environment: 
                        - ENV_VAR_1=ENV_VALUE_1
                        - ENV_VAR_2=ENV_VALUE_2
                    destination: some-destination
        "#;

        serde_yaml::from_str::<Feature>(feature).unwrap();
    }
}
