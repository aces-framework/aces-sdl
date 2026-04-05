pub mod common;
pub mod condition;
mod constants;
pub mod entity;
pub mod evaluation;
pub mod event;
pub mod feature;
pub mod goal;
mod helpers;
pub mod infrastructure;
pub mod inject;
mod library_item;
pub mod metric;
pub mod node;
pub mod script;
pub mod story;
pub mod training_learning_objective;
pub mod vulnerability;

use crate::helpers::Connection;
use anyhow::{anyhow, Ok, Result};
use condition::{Condition, Conditions};
use constants::MAX_LONG_NAME;
use depper::{Dependencies, DependenciesBuilder};
use entity::{Entities, Entity, Flatten};
use evaluation::{Evaluation, Evaluations};
use event::{Event, Events};
use feature::{Feature, Features};
use goal::Goals;
use infrastructure::{Infrastructure, InfrastructureHelper, Properties};
use inject::{Inject, Injects};
pub use library_item::LibraryItem;
use metric::{Metric, Metrics};
use node::{Node, NodeType, Nodes};
use script::{Script, Scripts};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use story::Stories;
use training_learning_objective::{TrainingLearningObjective, TrainingLearningObjectives};
use vulnerability::{Vulnerabilities, Vulnerability};

pub trait Formalize {
    fn formalize(&mut self) -> Result<()>;
}

#[derive(PartialEq, Debug, Serialize, Deserialize, Clone)]
pub struct Scenario {
    #[serde(alias = "Name", alias = "NAME")]
    pub name: String,
    #[serde(default, alias = "Description", alias = "DESCRIPTION")]
    pub description: Option<String>,
    #[serde(alias = "Nodes", alias = "NODES")]
    pub nodes: Option<Nodes>,
    #[serde(alias = "Features", alias = "FEATURES")]
    pub features: Option<Features>,
    #[serde(
        default,
        rename = "infrastructure",
        skip_serializing,
        alias = "Infrastructure",
        alias = "INFRASTRUCTURE"
    )]
    infrastructure_helper: Option<InfrastructureHelper>,
    #[serde(
        default,
        skip_deserializing,
        alias = "Infrastructure",
        alias = "INFRASTRUCTURE"
    )]
    pub infrastructure: Option<Infrastructure>,
    #[serde(alias = "Conditions", alias = "CONDITIONS")]
    pub conditions: Option<Conditions>,
    #[serde(alias = "Vulnerabilities", alias = "VULNERABILITIES")]
    pub vulnerabilities: Option<Vulnerabilities>,
    #[serde(alias = "Metrics", alias = "METRICS")]
    pub metrics: Option<Metrics>,
    #[serde(alias = "Evaluations", alias = "EVALUATIONS")]
    pub evaluations: Option<Evaluations>,
    #[serde(alias = "Tlos", alias = "TLOS")]
    pub tlos: Option<TrainingLearningObjectives>,
    #[serde(alias = "Entities", alias = "ENTITIES")]
    pub entities: Option<Entities>,
    #[serde(alias = "Goals", alias = "GOALS")]
    pub goals: Option<Goals>,
    #[serde(alias = "Injects", alias = "INJECTS")]
    pub injects: Option<Injects>,
    #[serde(alias = "Events", alias = "EVENTS")]
    pub events: Option<Events>,
    #[serde(alias = "Scripts", alias = "SCRIPTS")]
    pub scripts: Option<Scripts>,
    #[serde(alias = "Stories", alias = "STORIES")]
    pub stories: Option<Stories>,
}

impl Scenario {
    pub fn to_yaml(&self) -> Result<String> {
        serde_yaml::to_string(&self).map_err(|e| anyhow!("Failed to serialize to yaml: {}", e))
    }

    pub fn from_yaml(yaml: &str) -> Result<Self> {
        let mut schema: Self = serde_yaml::from_str(yaml)
            .map_err(|e| anyhow!("Failed to deserialize from yaml: {}", e))?;
        schema.formalize()?;
        Ok(schema)
    }

    pub fn get_node_dependencies(&self) -> Result<Dependencies> {
        let mut dependency_builder = Dependencies::builder();
        if let Some(nodes_value) = &self.nodes {
            for (node_name, _) in nodes_value.iter() {
                dependency_builder = dependency_builder.add_element(node_name.to_string(), vec![]);
            }
        }

        self.build_infrastructure_dependencies(dependency_builder)
    }

    pub fn get_feature_dependencies(&self) -> Result<Dependencies> {
        let mut dependency_builder = Dependencies::builder();
        if let Some(features_value) = &self.features {
            for (feature_name, _) in features_value.iter() {
                dependency_builder =
                    dependency_builder.add_element(feature_name.to_string(), vec![]);
            }
        }
        self.build_feature_dependencies(dependency_builder)
    }

    pub fn get_a_node_features_dependencies(
        &self,
        node_feature_name: &str,
    ) -> Result<Dependencies> {
        let mut dependency_builder = Dependencies::builder();

        if let Some(features_value) = &self.features {
            for (feature_name, _) in features_value.iter() {
                if feature_name.eq_ignore_ascii_case(node_feature_name) {
                    dependency_builder =
                        dependency_builder.add_element(feature_name.to_string(), vec![]);
                }
            }
        }
        self.build_a_single_features_dependencies(dependency_builder, node_feature_name)
    }

    fn build_infrastructure_dependencies(
        &self,
        mut dependency_builder: depper::DependenciesBuilder,
    ) -> Result<depper::Dependencies, anyhow::Error> {
        if let Some(infrastructure) = &self.infrastructure {
            for (node_name, infra_node) in infrastructure.iter() {
                let mut dependencies: Vec<String> = vec![];

                if let Some(links) = &infra_node.links {
                    for link in links {
                        dependencies.push(link.clone());
                    }
                }

                if let Some(node_dependencies) = &infra_node.dependencies {
                    dependencies.extend(node_dependencies.iter().cloned());
                }

                dependency_builder =
                    dependency_builder.add_element(node_name.clone(), dependencies);
            }
        }
        dependency_builder
            .build()
            .map_err(|e| anyhow!("Error building dependencies: {}", e))
    }

    fn build_feature_dependencies(
        &self,
        mut dependency_builder: depper::DependenciesBuilder,
    ) -> Result<Dependencies, anyhow::Error> {
        if let Some(features) = &self.features {
            for (feature_name, feature) in features.iter() {
                let mut dependencies: Vec<String> = vec![];

                if let Some(feature_dependencies) = &feature.dependencies {
                    dependencies.extend_from_slice(feature_dependencies.as_slice());
                }
                dependency_builder =
                    dependency_builder.add_element(feature_name.to_owned(), dependencies);
            }
        }
        dependency_builder.build()
    }

    fn build_a_single_features_dependencies(
        &self,
        mut dependency_builder: DependenciesBuilder,
        feature_name: &str,
    ) -> Result<Dependencies, anyhow::Error> {
        dependency_builder =
            self.get_a_parent_features_dependencies(feature_name, dependency_builder);

        dependency_builder.build()
    }

    pub fn get_a_parent_features_dependencies(
        &self,
        feature_name: &str,
        mut dependency_builder: DependenciesBuilder,
    ) -> DependenciesBuilder {
        if let Some(features) = &self.features {
            if let Some(feature) = features.get(feature_name) {
                if let Some(dependencies) = &feature.dependencies {
                    dependency_builder = dependency_builder
                        .add_element(feature_name.to_owned(), dependencies.to_vec());

                    for feature_name in dependencies.iter() {
                        dependency_builder = self
                            .get_a_parent_features_dependencies(feature_name, dependency_builder)
                    }
                    return dependency_builder;
                } else {
                    return dependency_builder.add_element(feature_name.to_owned(), vec![]);
                }
            }
        }
        dependency_builder
    }

    fn verify_dependencies(&self) -> Result<()> {
        self.get_node_dependencies()?;
        self.get_feature_dependencies()?;
        Ok(())
    }

    fn verify_switch_counts(&self) -> Result<()> {
        if let Some(infrastructure) = &self.infrastructure {
            if let Some(nodes) = &self.nodes {
                for (node_name, infra_node) in infrastructure.iter() {
                    if infra_node.count > 1 {
                        if let Some(node) = nodes.get(node_name) {
                            match node.type_field {
                                NodeType::Switch(_) => {
                                    return Err(anyhow!(
                                        "Node {} is a switch with a count higher than 1",
                                        node_name
                                    ));
                                }
                                _ => continue,
                            }
                        }
                    }
                }
            }
        }
        Ok(())
    }

    pub fn verify_nodes(&self) -> Result<()> {
        let feature_names = self
            .features
            .as_ref()
            .map(|feature_map| feature_map.keys().cloned().collect::<Vec<String>>());
        let condition_names = self
            .conditions
            .as_ref()
            .map(|condition_map| condition_map.keys().cloned().collect::<Vec<String>>());
        let inject_names = self
            .injects
            .as_ref()
            .map(|inject_map| inject_map.keys().cloned().collect::<Vec<String>>());
        let vulnerability_names = self
            .vulnerabilities
            .as_ref()
            .map(|vulnerability_map| vulnerability_map.keys().cloned().collect::<Vec<String>>());
        if let Some(nodes) = &self.nodes {
            for named_node in nodes.iter() {
                let name = named_node.0;
                if name.len() > MAX_LONG_NAME {
                    return Err(anyhow!(
                        "{} is too long, maximum node name length is {:?}",
                        name,
                        MAX_LONG_NAME
                    ));
                }
                match &named_node.1.type_field {
                    NodeType::VM(vm) => {
                        let named_vm = (named_node.0, vm);
                        Connection::<Feature>::validate_connections(&named_vm, &feature_names)?;
                        Connection::<Vulnerability>::validate_connections(
                            &named_vm,
                            &vulnerability_names,
                        )?;
                        Connection::<Condition>::validate_connections(
                            &(named_node.0, vm, &self.infrastructure),
                            &condition_names,
                        )?;
                        Connection::<Inject>::validate_connections(
                            &(named_node.0, vm, &self.infrastructure),
                            &inject_names,
                        )?;
                    }
                    _ => continue,
                }
            }
        }
        Ok(())
    }

    pub fn verify_infrastructure(&self) -> Result<()> {
        let node_names = self
            .nodes
            .as_ref()
            .map(|node_map| node_map.keys().cloned().collect::<HashSet<String>>())
            .unwrap_or_default();

        if let Some(infrastructure) = &self.infrastructure {
            for (infrastructure_name, infra_node) in infrastructure {
                if !node_names.contains(infrastructure_name) {
                    return Err(anyhow!(
                        "Infrastructure entry \"{}\" does not exist under Nodes",
                        infrastructure_name
                    ));
                }

                let mut all_dependencies = HashSet::new();
                if let Some(links) = &infra_node.links {
                    for link in links {
                        if !infrastructure.contains_key(link) {
                            return Err(anyhow!(
                                "Infrastructure entry \"{}\" does not exist under Infrastructure even though it is a dependency for \"{}\"",
                                link, infrastructure_name
                            ));
                        }
                        all_dependencies.insert(link.clone());
                    }
                }
                if let Some(dependencies) = &infra_node.dependencies {
                    for dependency in dependencies {
                        if !infrastructure.contains_key(dependency) {
                            return Err(anyhow!(
                                "Infrastructure entry \"{}\" does not exist under Infrastructure even though it is a dependency for \"{}\"",
                                dependency, infrastructure_name
                            ));
                        }
                        all_dependencies.insert(dependency.clone());
                    }
                }

                if let Some(Properties::Simple { cidr, gateway }) = &infra_node.properties {
                    if !cidr.contains(*gateway) {
                        return Err(anyhow!(
                            "Gateway {} is not within CIDR {} for node {}",
                            gateway,
                            cidr,
                            infrastructure_name
                        ));
                    }
                }

                if let Some(Properties::Complex(properties_list)) = &infra_node.properties {
                    if let Some(links) = &infra_node.links {
                        let link_set: HashSet<&String> = links.iter().collect();

                        for property_map in properties_list {
                            for (link, ip) in property_map {
                                if !link_set.contains(link) {
                                    return Err(anyhow!(
                                        "Property key '{}' in properties of node '{}' does not exist in its links: {:?}",
                                        link,
                                        infrastructure_name,
                                        links
                                    ));
                                }

                                if let Some(linked_node) = infrastructure.get(link) {
                                    if let Some(Properties::Simple { cidr, .. }) =
                                        &linked_node.properties
                                    {
                                        if !cidr.contains(*ip) {
                                            return Err(anyhow!(
                                                "IP address '{}' for '{}' in properties of node '{}' is not within the CIDR '{}' of the linked node '{}'",
                                                ip, link, infrastructure_name, cidr, link
                                            ));
                                        }
                                    } else {
                                        return Err(anyhow!(
                                            "Linked node '{}' does not have a valid CIDR in its properties",
                                            link
                                        ));
                                    }
                                } else {
                                    return Err(anyhow!(
                                        "Linked node '{}' referenced in properties of '{}' does not exist in the infrastructure",
                                        link, infrastructure_name
                                    ));
                                }
                            }
                        }
                    } else {
                        return Err(anyhow!(
                            "Links must be defined to validate Complex properties for node '{}'",
                            infrastructure_name
                        ));
                    }
                }
            }
        }

        Ok(())
    }

    pub fn verify_evaluations(&self) -> Result<()> {
        let metric_names = self
            .metrics
            .as_ref()
            .map(|metric_map| metric_map.keys().cloned().collect::<Vec<String>>());
        if let Some(evaluations) = &self.evaluations {
            for named_evaluation in evaluations.iter() {
                Connection::<Metric>::validate_connections(&named_evaluation, &metric_names)?;
                Evaluation::validate_evaluation_metric_scores(
                    named_evaluation.1,
                    self.metrics.as_ref(),
                )?;
            }
        }
        Ok(())
    }

    fn verify_training_learning_objectives(&self) -> Result<()> {
        let evaluation_names = self
            .evaluations
            .as_ref()
            .map(|evaluation_map| evaluation_map.keys().cloned().collect::<Vec<String>>());

        if let Some(training_learning_objectives) = &self.tlos {
            for named_tlo in training_learning_objectives {
                Connection::<Evaluation>::validate_connections(&named_tlo, &evaluation_names)?;
            }
        }
        Ok(())
    }

    fn verify_metrics(&self) -> Result<()> {
        let condition_names = self
            .conditions
            .as_ref()
            .map(|condition_map| condition_map.keys().cloned().collect::<Vec<String>>());

        let mut unique_conditions_under_metrics = HashSet::new();

        if let Some(metrics) = &self.metrics {
            for (metric_name, metric) in metrics.iter() {
                if let Some(condition) = &metric.condition {
                    if !unique_conditions_under_metrics.insert(condition) {
                        return Err(anyhow!(
                            "Duplicate condition '{}' found under metrics. Each condition must be unique for every metric.",
                            condition
                        ));
                    }
                }
                (metric_name, metric).validate_connections(&condition_names)?;
            }
        }
        Ok(())
    }

    fn verify_features(&self) -> Result<()> {
        let vulnerability_names = self
            .vulnerabilities
            .as_ref()
            .map(|vulnerability_map| vulnerability_map.keys().cloned().collect::<Vec<String>>());
        if let Some(features) = &self.features {
            for named_feature in features.iter() {
                named_feature.validate_connections(&vulnerability_names)?;
            }
        }
        Ok(())
    }

    fn verify_entities(&self) -> Result<()> {
        let vulnerability_names = self
            .vulnerabilities
            .as_ref()
            .map(|vulnerability_map| vulnerability_map.keys().cloned().collect::<Vec<String>>());
        let tlo_names = self
            .tlos
            .as_ref()
            .map(|tlo_map| tlo_map.keys().cloned().collect::<Vec<String>>());
        let event_names = self
            .events
            .as_ref()
            .map(|event_map| event_map.keys().cloned().collect::<Vec<String>>());

        if let Some(entities) = &self.entities {
            for named_entity in entities.flatten().iter() {
                Connection::<TrainingLearningObjective>::validate_connections(
                    &named_entity,
                    &tlo_names,
                )?;
                Connection::<Vulnerability>::validate_connections(
                    &named_entity,
                    &vulnerability_names,
                )?;
                Connection::<Event>::validate_connections(&named_entity, &event_names)?;
            }
        }
        Ok(())
    }

    fn verify_goals(&self) -> Result<()> {
        let tlo_names = self
            .tlos
            .as_ref()
            .map(|tlo_map| tlo_map.keys().cloned().collect::<Vec<String>>());
        if let Some(goals) = &self.goals {
            for goal in goals.iter() {
                goal.validate_connections(&tlo_names)?;
            }
        }
        Ok(())
    }

    fn verify_injects(&self) -> Result<()> {
        let entity_names = self.entities.as_ref().map(|entity_map| {
            entity_map
                .flatten()
                .keys()
                .cloned()
                .collect::<Vec<String>>()
        });
        let tlo_names = self
            .tlos
            .as_ref()
            .map(|tlo_map| tlo_map.keys().cloned().collect::<Vec<String>>());

        if let Some(injects) = &self.injects {
            for named_inject in injects.iter() {
                Connection::<Entity>::validate_connections(&named_inject, &entity_names)?;
                Connection::<TrainingLearningObjective>::validate_connections(
                    &named_inject,
                    &tlo_names,
                )?;
            }
        }
        Ok(())
    }

    fn verify_roles(&self) -> Result<()> {
        if let Some(nodes) = &self.nodes {
            let all_entity_names = self
                .entities
                .clone()
                .map(|entities| entities.flatten().keys().cloned().collect::<Vec<String>>());

            for (node_name, node) in nodes {
                match &node.type_field {
                    NodeType::VM(vm) => {
                        Connection::<Entity>::validate_connections(
                            &(node_name, &vm.roles),
                            &all_entity_names,
                        )?;

                        let feature_roles = vm.features.values().cloned().collect::<Vec<String>>();
                        Connection::<Node>::validate_connections(
                            &(node_name, &vm.roles),
                            &Some(feature_roles),
                        )?;
                        let condition_roles =
                            vm.conditions.values().cloned().collect::<Vec<String>>();
                        Connection::<Node>::validate_connections(
                            &(node_name, &vm.roles),
                            &Some(condition_roles),
                        )?;
                    }
                    _ => continue,
                }
            }
        }
        Ok(())
    }

    fn verify_events(&self) -> Result<()> {
        let condition_names = self
            .conditions
            .as_ref()
            .map(|entity_map| entity_map.keys().cloned().collect::<Vec<String>>());
        let inject_names = self
            .injects
            .as_ref()
            .map(|tlo_map| tlo_map.keys().cloned().collect::<Vec<String>>());

        if let Some(events) = &self.events {
            for named_event in events.iter() {
                Connection::<Condition>::validate_connections(&named_event, &condition_names)?;
                Connection::<Inject>::validate_connections(&named_event, &inject_names)?;
            }
        }
        Ok(())
    }

    fn verify_scripts(&self) -> Result<()> {
        let event_names = self
            .events
            .as_ref()
            .map(|entity_map| entity_map.keys().cloned().collect::<Vec<String>>());

        if let Some(scripts) = &self.scripts {
            for named_script in scripts.iter() {
                Connection::<Event>::validate_connections(&named_script, &event_names)?;
            }
        }
        Ok(())
    }

    fn verify_stories(&self) -> Result<()> {
        let script_names = self
            .scripts
            .as_ref()
            .map(|entity_map| entity_map.keys().cloned().collect::<Vec<String>>());

        if let Some(stories) = &self.stories {
            for named_story in stories.iter() {
                Connection::<Script>::validate_connections(&named_story, &script_names)?;
            }
        }
        Ok(())
    }
}

impl Formalize for Scenario {
    fn formalize(&mut self) -> Result<()> {
        if let Some(infrastructure_helper) = &self.infrastructure_helper {
            self.infrastructure = Some(Infrastructure::from(infrastructure_helper.clone()));
        }

        if let Some(mut nodes) = self.nodes.clone() {
            nodes.iter_mut().try_for_each(move |(_, node)| {
                if let NodeType::VM(ref mut vm) = node.type_field {
                    vm.formalize()?;
                }
                Ok(())
            })?;
            self.nodes = Some(nodes);
        }

        if let Some(mut infrastructure) = self.infrastructure.clone() {
            infrastructure
                .iter_mut()
                .try_for_each(move |(_, infra_node)| {
                    infra_node.formalize()?;
                    Ok(())
                })?;
            self.infrastructure = Some(infrastructure);
        }

        if let Some(features) = &mut self.features {
            features.iter_mut().try_for_each(move |(_, feature)| {
                feature.formalize()?;
                Ok(())
            })?;
        }

        if let Some(mut conditions) = self.conditions.clone() {
            conditions.iter_mut().try_for_each(move |(_, condition)| {
                condition.formalize()?;
                Ok(())
            })?;
            self.conditions = Some(conditions);
        }

        if let Some(mut metrics) = self.metrics.clone() {
            metrics.iter_mut().try_for_each(move |(_, metric)| {
                metric.formalize()?;
                Ok(())
            })?;
            self.metrics = Some(metrics);
        }

        if let Some(mut evaluations) = self.evaluations.clone() {
            evaluations
                .iter_mut()
                .try_for_each(move |(_, evaluation)| {
                    evaluation.formalize()?;
                    Ok(())
                })?;
            self.evaluations = Some(evaluations);
        }

        if let Some(mut vulnerabilities) = self.vulnerabilities.clone() {
            vulnerabilities
                .iter_mut()
                .try_for_each(move |(_, vulnerability)| {
                    vulnerability.formalize()?;
                    Ok(())
                })?;
            self.vulnerabilities = Some(vulnerabilities);
        }

        if let Some(mut goals) = self.goals.clone() {
            goals.iter_mut().try_for_each(move |(_, goal)| {
                goal.formalize()?;
                Ok(())
            })?;
            self.goals = Some(goals);
        }

        if let Some(mut injects) = self.injects.clone() {
            injects.iter_mut().try_for_each(move |(_, inject)| {
                inject.formalize()?;
                Ok(())
            })?;
            self.injects = Some(injects);
        }

        if let Some(mut events) = self.events.clone() {
            events.iter_mut().try_for_each(move |(_, event)| {
                event.formalize()?;
                Ok(())
            })?;
            self.events = Some(events);
        }

        if let Some(mut scripts) = self.scripts.clone() {
            scripts.iter_mut().try_for_each(move |(_, script)| {
                script.formalize()?;
                Ok(())
            })?;
            self.scripts = Some(scripts);
        }

        if let Some(mut stories) = self.stories.clone() {
            stories.iter_mut().try_for_each(move |(_, story)| {
                story.formalize()?;
                Ok(())
            })?;
            self.stories = Some(stories);
        }

        self.verify_entities()?;
        self.verify_goals()?;
        self.verify_nodes()?;
        self.verify_infrastructure()?;
        self.verify_evaluations()?;
        self.verify_switch_counts()?;
        self.verify_features()?;
        self.verify_dependencies()?;
        self.verify_metrics()?;
        self.verify_training_learning_objectives()?;
        self.verify_roles()?;
        self.verify_injects()?;
        self.verify_events()?;
        self.verify_scripts()?;
        self.verify_stories()?;
        Ok(())
    }
}

pub fn parse_sdl(sdl_string: &str) -> Result<Scenario> {
    Scenario::from_yaml(sdl_string)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn can_parse_minimal_sdl() {
        let minimal_sdl = r#"
                name: test-scenario

        "#;
        let parsed_schema = parse_sdl(minimal_sdl).unwrap();
        insta::assert_yaml_snapshot!(parsed_schema);
    }

    #[test]
    fn includes_nodes() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                win10:
                    type: VM
                    description: win-10-description
                    source: windows10
                    resources:
                        ram: 4 gib
                        cpu: 2
                deb10:
                    type: VM
                    description: deb-10-description
                    source:
                        name: debian10
                        version: '*'
                    resources:
                        ram: 2 gib
                        cpu: 1

        "#;
        let nodes = parse_sdl(sdl).unwrap().nodes;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(nodes);
        });
    }

    #[test]
    fn includes_infrastructure() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                win10:
                    type: VM
                    description: win-10-description
                    source: windows10
                    resources:
                        ram: 4 gib
                        cpu: 2
                deb10:
                    type: VM
                    description: deb-10-description
                    source:
                        name: debian10
                        version: '*'
                    resources:
                        ram: 2 gib
                        cpu: 1
            infrastructure:
                win10:
                    count: 10
                    dependencies:
                        - deb10
                deb10: 3

        "#;
        let infrastructure = parse_sdl(sdl).unwrap().infrastructure;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(infrastructure);
        });
    }

    #[test]
    fn includes_features() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            features:
                my-cool-service:
                    type: service
                    source: some-service
                my-cool-config:
                    type: configuration
                    source: some-configuration
                    dependencies:
                        - my-cool-service
                my-cool-artifact:
                    type: artifact
                    source:
                        name: dl_library
                        version: 1.2.3
                    dependencies:
                        - my-cool-service
        "#;
        let features = parse_sdl(sdl).unwrap().features;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(features);
        });
    }

    #[test]
    #[should_panic(expected = "VM \"win-10\" has Features but none found under Scenario")]
    fn feature_missing_from_scenario() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                win-10:
                    type: VM
                    source: windows10
                    resources:
                        ram: 4 GiB
                        cpu: 2
                    roles:
                        moderator: "name"
                    features:
                        my-cool-service: "moderator"

        "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(expected = "Role admin not found under for Node win-10's roles")]
    fn feature_role_missing_from_node() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                win-10:
                    type: VM
                    source: windows10
                    resources:
                        ram: 4 GiB
                        cpu: 2
                    roles:
                        moderator: "name"
                    features:
                        my-cool-service: "admin"
            features:
                my-cool-service:
                    type: service
                    source: some-service

        "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    fn includes_conditions_nodes_and_infrastructure() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                win10:
                    type: VM
                    description: win-10-description
                    source: windows10
                    resources:
                        ram: 4 gib
                        cpu: 2
                    roles:
                        admin: "username"
                    conditions:
                        condition-1: "admin"
                deb10:
                    type: VM
                    description: deb-10-description
                    source:
                        name: debian10
                        version: '*'
                    resources:
                        ram: 2 gib
                        cpu: 1
                    roles:
                        admin: "username"
                        moderator: "name"
                    conditions:
                        condition-2: "moderator"
                        condition-3: "admin"
            infrastructure:
                win10:
                    count: 1
                    dependencies:
                        - deb10
                deb10: 1
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30
                condition-2:
                    source: digital-library-package
                condition-3:
                    command: executable/path.sh
                    interval: 30

        "#;
        let conditions = parse_sdl(sdl).unwrap();
        insta::with_settings!({sort_maps => true}, {
                insta::assert_yaml_snapshot!(conditions);
        });
    }

    #[test]
    #[should_panic(
        expected = "Node \"win10\" can not have count bigger than 1, if it has conditions defined"
    )]
    fn condition_vm_count_in_infrastructure_over_1() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                win10:
                    type: VM
                    description: win-10-description
                    source: windows10
                    resources:
                        ram: 4 gib
                        cpu: 2
                    roles:
                        admin: "username"
                    conditions:
                        condition-1: "admin"
                deb10:
                    type: VM
                    description: deb-10-description
                    source:
                        name: debian10
                        version: '*'
                    resources:
                        ram: 2 gib
                        cpu: 1
            infrastructure:
                win10:
                    count: 3
                    dependencies:
                        - deb10
                deb10: 1
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30
        "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(expected = "Node \"win10\" has Conditions but none found under Scenario")]
    fn condition_doesnt_exist() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                win10:
                    type: VM
                    description: win-10-description
                    source: windows10
                    resources:
                        ram: 4 gib
                        cpu: 2
                    roles:
                        admin: "username"
                    conditions:
                        condition-1: "admin"
            infrastructure:
                win10: 1

        "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(expected = "Role admin not found under for Node win-10's roles")]
    fn condition_role_missing_from_node() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                win-10:
                    type: VM
                    source: windows10
                    resources:
                        ram: 4 GiB
                        cpu: 2
                    roles:
                        moderator: "name"
                    conditions:
                        condition-1: "admin"
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30

        "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    #[should_panic(
        expected = "my-really-really-superlong-non-compliant-name is too long, maximum node name length is 35"
    )]
    fn too_long_node_name_is_disallowed() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            nodes:
                my-really-really-superlong-non-compliant-name:
                    type: VM
                    description: win-10-description
                    source: windows10
                    resources:
                        ram: 4 gib
                        cpu: 2
        "#;
        parse_sdl(sdl).unwrap();
    }

    #[test]
    fn parent_features_dependencies_are_built_correctly() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            features:
                parent-service:
                    type: Service
                    source: some-service
                    dependencies:
                        - child-service
                        - child-config
                child-config:
                    type: Configuration
                    source: some-config
                child-service:
                    type: Service
                    source:
                        name: child-service
                        version: 1.0.0
                    dependencies:
                        - grandchild-config
                        - grandchild-artifact
                grandchild-config:
                    type: Configuration
                    source:
                        name: some-config
                        version: 1.0.0
                grandchild-artifact:
                    type: Artifact
                    source:
                        name: cool-artifact
                        version: 1.0.0
                    dependencies:
                        - grandgrandchild-artifact
                grandgrandchild-artifact:
                    type: Artifact
                    source: some-artifact
                    dependencies:
                        - grandchild-config
                unrelated-artifact:
                    type: Artifact
                    source: some-artifact
                    dependencies:
                        - very-unrelated-artifact
                very-unrelated-artifact:
                    type: Artifact
                    source: some-artifact
        "#;
        let scenario = parse_sdl(sdl).unwrap();
        let dependencies = scenario
            .get_a_node_features_dependencies("parent-service")
            .unwrap();

        insta::assert_debug_snapshot!(dependencies.generate_tranches().unwrap());
    }

    #[test]
    #[should_panic(
        expected = "Duplicate condition 'condition-1' found under metrics. Each condition must be unique for every metric."
    )]
    fn condition_used_by_multiple_metrics() {
        let sdl = r#"
            name: test-scenario
            description: some-description
            metrics:
                metric-1:
                    type: CONDITIONAL
                    max-score: 10
                    condition: condition-1
                metric-2:
                    type: CONDITIONAL
                    max-score: 10
                    condition: condition-1
            conditions:
                condition-1:
                    command: executable/path.sh
                    interval: 30
        "#;
        parse_sdl(sdl).unwrap();
    }
}
