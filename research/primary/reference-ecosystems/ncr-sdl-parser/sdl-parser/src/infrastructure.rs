use crate::constants::{default_node_count, MINIMUM_NODE_COUNT};
use crate::helpers::Connection;
use crate::Formalize;
use anyhow::{anyhow, Result};
use ipnetwork::IpNetwork;
use serde::{Deserialize, Deserializer, Serialize};
use std::collections::{HashMap, HashSet};
use std::fmt;
use std::net::IpAddr;

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone, Default)]
pub struct InfraNode {
    #[serde(default, alias = "Name", alias = "NAME")]
    pub name: Option<String>,
    #[serde(default = "default_node_count", alias = "Count", alias = "COUNT")]
    pub count: i32,
    #[serde(
        default,
        alias = "Links",
        alias = "LINKS",
        deserialize_with = "deserialize_unique_list"
    )]
    pub links: Option<Vec<String>>,
    #[serde(
        default,
        alias = "Dependencies",
        alias = "DEPENDENCIES",
        alias = "dependencies",
        deserialize_with = "deserialize_unique_list"
    )]
    pub dependencies: Option<Vec<String>>,
    #[serde(
        default,
        alias = "Properties",
        alias = "PROPERTIES",
        alias = "properties",
        deserialize_with = "deserialize_properties"
    )]
    pub properties: Option<Properties>,
    #[serde(alias = "Description", alias = "DESCRIPTION", alias = "description")]
    pub description: Option<String>,
}

impl InfraNode {
    pub fn new(potential_count: Option<i32>) -> Self {
        Self {
            count: match potential_count {
                Some(count) => count,
                None => default_node_count(),
            },
            ..Default::default()
        }
    }
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
#[serde(untagged)]
pub enum Properties {
    Simple { cidr: IpNetwork, gateway: IpAddr },
    Complex(Vec<HashMap<String, IpAddr>>),
}

#[derive(PartialEq, Eq, Debug, Deserialize, Clone)]
#[serde(untagged)]
pub enum HelperNode {
    Empty,
    Short(i32),
    Long(InfraNode),
    Nested {
        count: Option<i32>,
        #[serde(default, deserialize_with = "deserialize_unique_list")]
        links: Option<Vec<String>>,
        #[serde(default, deserialize_with = "deserialize_unique_list")]
        dependencies: Option<Vec<String>>,
        #[serde(default, deserialize_with = "deserialize_properties")]
        properties: Option<Properties>,
    },
}

#[derive(PartialEq, Eq, Debug, Deserialize, Clone)]
pub struct InfrastructureHelper(pub HashMap<String, HelperNode>);

impl From<HelperNode> for InfraNode {
    fn from(helper: HelperNode) -> Self {
        match helper {
            HelperNode::Empty => InfraNode::default(),
            HelperNode::Short(count) => InfraNode {
                count,
                ..Default::default()
            },
            HelperNode::Long(node) => node,
            HelperNode::Nested {
                count,
                links,
                dependencies,
                properties,
            } => InfraNode {
                count: count.unwrap_or_else(default_node_count),
                links,
                dependencies,
                properties,
                ..Default::default()
            },
        }
    }
}

impl From<InfrastructureHelper> for Infrastructure {
    fn from(helper_infrastructure: InfrastructureHelper) -> Self {
        helper_infrastructure
            .0
            .into_iter()
            .map(|(node_name, helper_node)| {
                let mut infra_node: InfraNode = helper_node.into();
                infra_node.formalize().unwrap();
                (node_name, infra_node)
            })
            .collect()
    }
}

pub type Infrastructure = HashMap<String, InfraNode>;

impl Connection<Infrastructure> for String {
    fn validate_connections(&self, potential_node_names: &Option<Vec<String>>) -> Result<()> {
        if let Some(node_names) = potential_node_names {
            if !node_names.contains(self) {
                return Err(anyhow!(
                    "Infrastructure entry '{}' does not exist under Nodes",
                    self
                ));
            }
        }
        Ok(())
    }
}

impl Formalize for InfraNode {
    fn formalize(&mut self) -> Result<()> {
        if self.count < MINIMUM_NODE_COUNT {
            return Err(anyhow!(
                "Infrastructure Count field cannot be less than {MINIMUM_NODE_COUNT}"
            ));
        }
        Ok(())
    }
}

fn deserialize_unique_list<'de, D>(deserializer: D) -> Result<Option<Vec<String>>, D::Error>
where
    D: Deserializer<'de>,
{
    struct UniqueListVisitor;

    impl<'de> serde::de::Visitor<'de> for UniqueListVisitor {
        type Value = Vec<String>;

        fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
            formatter.write_str("a list of unique strings")
        }

        fn visit_seq<A>(self, mut seq: A) -> Result<Self::Value, A::Error>
        where
            A: serde::de::SeqAccess<'de>,
        {
            let mut items = HashSet::new();
            let mut result = Vec::new();

            while let Some(value) = seq.next_element::<String>()? {
                if items.contains(&value) {
                    return Err(serde::de::Error::custom(format!(
                        "duplicate value found: {}",
                        value
                    )));
                }
                items.insert(value.clone());
                result.push(value);
            }

            Ok(result)
        }
    }

    deserializer.deserialize_seq(UniqueListVisitor).map(Some)
}

fn deserialize_properties<'de, D>(deserializer: D) -> Result<Option<Properties>, D::Error>
where
    D: Deserializer<'de>,
{
    #[derive(Deserialize)]
    struct SimpleProperties {
        cidr: IpNetwork,
        gateway: IpAddr,
    }

    #[derive(Deserialize)]
    #[serde(untagged)]
    enum RawProperties {
        Simple(SimpleProperties),
        Complex(Vec<HashMap<String, String>>),
    }

    match RawProperties::deserialize(deserializer)? {
        RawProperties::Simple(simple) => Ok(Some(Properties::Simple {
            cidr: simple.cidr,
            gateway: simple.gateway,
        })),
        RawProperties::Complex(complex) => {
            let list = complex
                .into_iter()
                .map(|map| {
                    map.into_iter()
                        .map(|(key, value)| {
                            let ip = value.parse::<IpAddr>().map_err(serde::de::Error::custom)?;
                            Ok((key, ip))
                        })
                        .collect::<Result<HashMap<String, IpAddr>, _>>()
                })
                .collect::<Result<Vec<HashMap<String, IpAddr>>, _>>()?;
            Ok(Some(Properties::Complex(list)))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse_sdl;

    #[test]
    fn infranode_count_longhand_is_parsed() {
        let sdl = r#"
            count: 23
        "#;
        let infra_node = serde_yaml::from_str::<InfraNode>(sdl).unwrap();
        insta::assert_debug_snapshot!(infra_node);
    }

    #[test]
    fn infranode_count_shorthand_is_parsed() {
        let sdl = r#"
            23
        "#;
        let infra_node: InfraNode = serde_yaml::from_str::<HelperNode>(sdl).unwrap().into();
        insta::assert_debug_snapshot!(infra_node);
    }

    #[test]
    fn infranode_with_links_and_dependencies_is_parsed() {
        let sdl = r#"
            count: 25
            links:
                - switch-2              
            dependencies:
                - windows-10
                - windows-10-vuln-1
        "#;
        let infra_node = serde_yaml::from_str::<InfraNode>(sdl).unwrap();
        insta::assert_debug_snapshot!(infra_node);
    }

    #[test]
    fn infranode_with_default_count_is_parsed() {
        let sdl = r#"
            links:
                - switch-1
            dependencies:
                - windows-10
                - windows-10-vuln-1 
        "#;
        let infra_node = serde_yaml::from_str::<InfraNode>(sdl).unwrap();
        insta::assert_debug_snapshot!(infra_node);
    }

    #[test]
    fn simple_infrastructure_is_parsed() {
        let sdl = r#"
            windows-10-vuln-1:
                count: 10
                description: "A vulnerable Windows 10 machine"
            debian-2:
                count: 4
                description: "A Debian server"     
        "#;
        let infrastructure = serde_yaml::from_str::<Infrastructure>(sdl).unwrap();
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(infrastructure);
        });
    }

    #[test]
    fn simple_infrastructure_with_shorthand_is_parsed() {
        let sdl = r#"
            windows-10-vuln-2:
                count: 10
            windows-10-vuln-1: 10
            ubuntu-10: 5
        "#;
        let infrastructure_helper = serde_yaml::from_str::<InfrastructureHelper>(sdl).unwrap();
        let infrastructure: Infrastructure = infrastructure_helper.into();

        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(infrastructure);
        });
    }

    #[test]
    fn bigger_infrastructure_is_parsed() {
        let sdl = r#"
            switch-1: 1
            windows-10: 3
            windows-10-vuln-1:
                count: 1
            switch-2:
                count: 2
                links:
                    - switch-1
            ubuntu-10:
                links:
                    - switch-1
                dependencies:
                    - windows-10
                    - windows-10-vuln-1
        "#;
        let infrastructure_helper = serde_yaml::from_str::<InfrastructureHelper>(sdl).unwrap();
        let infrastructure: Infrastructure = infrastructure_helper.into();

        insta::with_settings!({sort_maps => true}, {
            insta::assert_yaml_snapshot!(infrastructure);
        });
    }

    #[test]
    fn sdl_keys_are_valid_in_lowercase_uppercase_capitalized() {
        let sdl = r#"
            switch-1: 1
            windows-10: 3
            windows-10-vuln-1:
                Count: 1
                DEPENDENCIES:
                    - windows-10
            switch-2:
                COUNT: 2
                Links:
                    - switch-1
            ubuntu-10:
                LINKS:
                    - switch-1
                Dependencies:
                    - windows-10
                    - windows-10-vuln-1
        "#;
        let infrastructure_helper = serde_yaml::from_str::<InfrastructureHelper>(sdl).unwrap();
        let infrastructure: Infrastructure = infrastructure_helper.into();

        insta::with_settings!({sort_maps => true}, {
            insta::assert_yaml_snapshot!(infrastructure);
        });
    }

    #[test]
    fn infrastructure_with_links_and_properties() {
        let sdl = r#"
switch-1:
    count: 1
    properties:
        cidr: 10.10.10.0/24
        gateway: 10.10.10.1
windows-10: 3
windows-10-vuln-1:
    count: 1
    links:
        - switch-1
    properties:
        - switch-1: 10.10.10.10
switch-2:
    count: 2
    links:
        - switch-1
ubuntu-10:
    links:
        - switch-1
    dependencies:
        - windows-10
        - windows-10-vuln-1

        "#;

        let infrastructure_helper = serde_yaml::from_str::<InfrastructureHelper>(sdl).unwrap();
        let infrastructure: Infrastructure = infrastructure_helper.into();

        insta::with_settings!({sort_maps => true}, {
            insta::assert_yaml_snapshot!(infrastructure);
        });
    }

    #[test]
    fn empty_count_is_allowed() {
        let sdl = r#"
            switch-1:
        "#;
        serde_yaml::from_str::<InfrastructureHelper>(sdl).unwrap();
    }

    #[should_panic(expected = "Infrastructure Count field cannot be less than 1")]
    #[test]
    fn infranode_with_negative_count_is_rejected() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                win-10:
                    type: VM
                    resources:
                        ram: 2 gib
                        cpu: 2
                    source: windows10
            infrastructure:
                win-10: -1
        "#;
        parse_sdl(sdl).unwrap();
    }

    #[should_panic(expected = "Infrastructure entry \"debian\" does not exist under Nodes")]
    #[test]
    fn infranode_with_unknown_name_is_rejected() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                win-10:
                    type: VM
                    resources:
                        ram: 2 gib
                        cpu: 2
                    source: windows10
            infrastructure:
                debian: 1
        "#;
        parse_sdl(sdl).unwrap();
    }

    #[should_panic(
        expected = "Infrastructure entry \"main-switch\" does not exist under Infrastructure even though it is a dependency for \"win-10\""
    )]
    #[test]
    fn error_on_missing_infrastructure_link() {
        let sdl = r#"
        name: test-scenario
        description: some-description
        nodes:
            win-10:
                type: VM
                resources:
                    ram: 2 gib
                    cpu: 2
                source: windows10
            main-switch:
                type: Switch
        infrastructure:
            win-10:
                count: 1
                links:
                    - main-switch
        "#;

        parse_sdl(sdl).unwrap();
    }

    #[should_panic(
        expected = "Infrastructure entry \"router\" does not exist under Infrastructure even though it is a dependency for \"win-10\""
    )]
    #[test]
    fn error_on_missing_infrastructure_dependency() {
        let sdl = r#"
        name: test-scenario
        description: some-description
        nodes:
            win-10:
                type: VM
                resources:
                    ram: 2 gib
                    cpu: 2
                source: windows10
            router:
                type: VM
                resources:
                    ram: 2 gib
                    cpu: 2
                source: debian11
        infrastructure: 
            win-10:
                count: 1
                dependencies:
                - router
        "#;

        parse_sdl(sdl).unwrap();
    }

    #[should_panic(
        expected = "IP address '10.20.10.10' for 'main-switch' in properties of node 'win-10' is not within the CIDR '10.10.10.0/24' of the linked node 'main-switch'"
    )]
    #[test]
    fn error_on_wrong_ip_in_infranode_properties() {
        let sdl = r#"
        name: test-scenario
        description: some-description
        nodes:
            win-10:
                type: VM
                resources:
                    ram: 2 gib
                    cpu: 2
                source: windows10
            main-switch:
                type: Switch
        infrastructure:
            main-switch:
                count: 1
                properties:
                    cidr: 10.10.10.0/24
                    gateway: 10.10.10.1
            win-10:
                count: 1
                links:
                    - main-switch
                properties:
                    - main-switch: 10.20.10.10
        "#;

        parse_sdl(sdl).unwrap();
    }
}
