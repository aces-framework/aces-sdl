use anyhow::{Ok, Result};
use serde::{Deserialize, Serialize};

use crate::{node::NodeType, parse_sdl};

#[derive(PartialEq, Debug, Serialize, Deserialize, Clone, Ord, PartialOrd, Eq)]
pub struct LibraryItem {
    pub name: String,
    pub version: String,
}

impl LibraryItem {
    #[allow(dead_code)]
    fn new(name: String, version: String) -> Self {
        Self { name, version }
    }
}

#[allow(dead_code)]
pub fn generate_package_list(sdl_string: &str) -> Result<Vec<LibraryItem>> {
    let nodes = parse_sdl(sdl_string)?.nodes;
    let mut result = Vec::new();

    if let Some(nodes) = nodes {
        for (_, node) in nodes {
            match node.type_field {
                NodeType::VM(vm) => {
                    if let Some(source) = &vm.source {
                        result.push(LibraryItem::new(
                            source.name.clone(),
                            source.version.clone(),
                        ));
                    }
                }
                _ => continue,
            }
        }
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generate_package_list_based_on_sdl() {
        let node_sdl = r#"
            name: test-scenario
            nodes:
                win10-1:
                    type: VM
                    description: win10 node for OCR
                    resources:
                        ram: 4 gib
                        cpu: 4
                    source:
                        name: basic-windows10
                        version: "1.0"
                deb-10-1:
                    type: VM
                    description: deb-10-description
                    resources:
                        ram: 4 gib
                        cpu: 4
                    source:
                        name: debian10
                        version: "1.2.4"
                win-10-2:
                    type: VM
                    description: win10 node for OCR
                    resources:
                        ram: 4 gib
                        cpu: 4
                    source: windows10-template
                win-10-3:
                    type: VM
                    description: win10 node for OCR
                    resources:
                        ram: 4 gib
                        cpu: 4
                    source: windows10
        "#;
        let mut library_items = generate_package_list(node_sdl).unwrap();
        library_items.sort();

        insta::assert_debug_snapshot!(library_items);
    }
}
