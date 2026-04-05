pub(crate) mod enums;

use crate::constants::ASSETS_REQUIRED_PACKAGE_TYPES;
use crate::project::enums::{Architecture, OperatingSystem};
use anyhow::{anyhow, Ok, Result};
use fancy_regex::Regex;
use serde::{Deserialize, Deserializer, Serialize};
use std::fmt::Formatter;
use std::str::FromStr;
use std::{fmt, fs::File, io::Read, path::Path};

use self::enums::VirtualMachineType;

pub fn create_project_from_toml_path(toml_path: &Path) -> Result<Project, anyhow::Error> {
    let mut toml_file = File::open(toml_path)?;
    let mut contents = String::new();
    toml_file.read_to_string(&mut contents)?;
    let deserialized_toml: Project = toml::from_str(&contents)?;
    Ok(deserialized_toml)
}

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq, Clone)]
pub struct Project {
    pub package: Body,
    pub content: Content,
    #[serde(rename = "virtual-machine")]
    pub virtual_machine: Option<VirtualMachine>,
    pub feature: Option<Feature>,
    pub condition: Option<Condition>,
    pub event: Option<Event>,
    pub inject: Option<Inject>,
    pub malware: Option<Malware>,
    pub exercise: Option<Exercise>,
    pub banner: Option<Banner>,
    pub other: Option<Other>,
}

impl Project {
    pub fn validate_assets(&self) -> Result<()> {
        let package_type = &self.content.content_type;

        if !ASSETS_REQUIRED_PACKAGE_TYPES.contains(package_type) {
            return Ok(());
        }

        if let Some(assets) = &self.package.assets {
            if assets.is_empty() {
                return Err(anyhow!(
                    "Assets are required for '{package_type}' package type"
                ));
            }
            for (index, asset) in assets.iter().enumerate() {
                if asset.len() < 2 {
                    return Err(anyhow!(
                            "Package.assets[{index}] is invalid.
                            Expected format: [\"relative source path\", \"absolute destination path\", optional file permissions]
                            E.g. [\"files/file.sh\", \"/usr/local/bin/renamed_file.sh\", \"755\"] or [\"files/file.sh\", \"/usr/local/bin/\"]"
                        ));
                }
                if asset.len() > 2 {
                    let re = Regex::new(r"^[0-7]{3,4}$").unwrap();
                    if !(re.is_match(&asset[2])?) {
                        return Err(anyhow!(
                            "Package.assets[{index}][2] is invalid.
                            Expected format: 3-4 octal values
                            E.g. \"755\" or \"0777\""
                        ));
                    }
                }
            }
        } else {
            return Err(anyhow!(
                "Assets are required for '{package_type}' package type"
            ));
        }

        Ok(())
    }

    pub fn validate_asset_files(&self, package_path: &Path) -> Result<()> {
        if let Some(assets) = &self.package.assets {
            for asset in assets {
                let asset_path = package_path.join(&asset[0]);
                if !asset_path.exists() {
                    return Err(anyhow!(
                        "Asset '{}' not found in package files",
                        asset_path.display()
                    ));
                }
            }
        } else {
            return Err(anyhow!("Package has no assets"));
        }

        Ok(())
    }

    pub fn validate_content(&mut self) -> Result<()> {
        let mut content_types = vec![
            self.virtual_machine.as_ref().map(|_| ContentType::VM),
            self.feature.as_ref().map(|_| ContentType::Feature),
            self.condition.as_ref().map(|_| ContentType::Condition),
            self.inject.as_ref().map(|_| ContentType::Inject),
            self.event.as_ref().map(|_| ContentType::Event),
            self.malware.as_ref().map(|_| ContentType::Malware),
            self.exercise.as_ref().map(|_| ContentType::Exercise),
            self.banner.as_ref().map(|_| ContentType::Banner),
            self.other.as_ref().map(|_| ContentType::Other),
        ];
        content_types.retain(|potential_content_types| potential_content_types.is_some());
        if content_types.len() > 1 {
            return Err(anyhow!(
                "Multiple content types per package are not supported"
            ));
        }

        match self.content.content_type {
            ContentType::VM => {
                if self.virtual_machine.is_none() {
                    return Err(anyhow!("Virtual machine package info not found"));
                }
            }
            ContentType::Feature => {
                if self.feature.is_none() {
                    return Err(anyhow!("Feature package info not found"));
                }
            }
            ContentType::Condition => {
                if self.condition.is_none() {
                    return Err(anyhow!("Condition package info not found"));
                }
            }
            ContentType::Inject => {
                if self.inject.is_none() {
                    return Err(anyhow!("Inject package info not found"));
                }
            }
            ContentType::Event => {
                if self.event.is_none() {
                    return Err(anyhow!("Event package info not found"));
                }
            }
            ContentType::Malware => {
                if self.malware.is_none() {
                    return Err(anyhow!("Malware package info not found"));
                }
            }
            ContentType::Exercise => {
                if self.exercise.is_none() {
                    return Err(anyhow!("Exercise package info not found"));
                }
            }
            ContentType::Banner => {
                if self.banner.is_none() {
                    return Err(anyhow!("Banner package info not found"));
                }
            }
            ContentType::Other => {
                if self.other.is_none() {
                    return Err(anyhow!("Other package info not found"));
                }
            }
        }

        if let Some(preview) = &self.content.preview {
            for preview_item in preview {
                match preview_item {
                    Preview::Picture(paths) | Preview::Video(paths) | Preview::Code(paths) => {
                        for path in paths {
                            if !Path::new(path).exists() {
                                return Err(anyhow!("Preview file \"{path}\" not found"));
                            }
                        }
                    }
                }
            }
        }

        Ok(())
    }

    pub fn validate_files(&self, package_path: &Path) -> Result<()> {
        let readme_path = package_path.join(&self.package.readme);
        if !readme_path.exists() {
            return Err(anyhow!("Readme not found"));
        }

        if let Some(vm) = &self.virtual_machine {
            let file_path = package_path.join(&vm.file_path);
            if !file_path.exists() {
                return Err(anyhow!("Virtual machine file not found"));
            }
        }

        if let Some(event) = &self.event {
            let file_path = package_path.join(&event.file_path);
            if !file_path.exists() {
                return Err(anyhow!("Event file not found"));
            }
        }

        if let Some(exercise) = &self.exercise {
            let file_path = package_path.join(&exercise.file_path);
            if !file_path.exists() {
                return Err(anyhow!("Exercise file not found"));
            }
        }

        if let Some(banner) = &self.banner {
            let file_path = package_path.join(&banner.file_path);
            if !file_path.exists() {
                return Err(anyhow!("Banner file not found"));
            }
        }

        if ASSETS_REQUIRED_PACKAGE_TYPES.contains(&self.content.content_type) {
            self.validate_asset_files(package_path)?;
        }
        Ok(())
    }

    pub fn print_inspect_message(&self, pretty: bool) -> Result<()> {
        if pretty {
            println!("{}", serde_json::to_string_pretty(&self)?);
        } else {
            println!("{}", serde_json::to_string(&self)?);
        }
        Ok(())
    }
}

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq, Clone)]
pub struct Account {
    pub name: String,
    pub password: String,
    pub private_key: Option<String>,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct VirtualMachine {
    pub accounts: Option<Vec<Account>>,
    #[serde(default)]
    pub operating_system: Option<OperatingSystem>,
    #[serde(default)]
    pub architecture: Option<Architecture>,
    #[serde(rename = "type")]
    pub virtual_machine_type: VirtualMachineType,
    pub file_path: String,
}

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
    #[serde(rename = "type", alias = "Type", alias = "TYPE")]
    pub feature_type: FeatureType,
    #[serde(alias = "Action", alias = "ACTION")]
    pub action: Option<String>,
    #[serde(alias = "Restarts", alias = "RESTARTS", default)]
    pub restarts: bool,
    #[serde(rename = "delete", alias = "Delete", alias = "DELETE", default)]
    pub delete_action: Option<String>,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Event {
    #[serde(alias = "File_path", alias = "FILE_PATH")]
    pub file_path: String,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Condition {
    #[serde(alias = "Action", alias = "ACTION")]
    pub action: String,
    #[serde(alias = "Interval", alias = "INTERVAL")]
    pub interval: u32,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Inject {
    #[serde(alias = "Action", alias = "ACTION")]
    pub action: Option<String>,
    #[serde(alias = "Restarts", alias = "RESTARTS", default)]
    pub restarts: bool,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Malware {
    #[serde(alias = "Action", alias = "ACTION")]
    pub action: String,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Exercise {
    #[serde(alias = "File_path", alias = "FILE_PATH")]
    pub file_path: String,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Banner {
    #[serde(alias = "File_path", alias = "FILE_PATH")]
    pub file_path: String,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Other {}

#[derive(Debug)]
enum Values<T> {
    Null,
    Value(T),
}

impl<T> From<Option<T>> for Values<T> {
    fn from(opt: Option<T>) -> Values<T> {
        match opt {
            Some(v) => Values::Value(v),
            None => Values::Null,
        }
    }
}

impl<'de, T> Deserialize<'de> for Values<T>
where
    T: Deserialize<'de>,
{
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        Option::deserialize(deserializer).map(Into::into)
    }
}

impl FromStr for VirtualMachineType {
    type Err = anyhow::Error;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_ascii_lowercase().as_str() {
            "ova" => Ok(VirtualMachineType::OVA),
            "qcow2" => Ok(VirtualMachineType::QCOW2),
            "raw" => Ok(VirtualMachineType::RAW),
            _ => Err(anyhow!("Invalid virtual machine type: {}", s)),
        }
    }
}

impl<'de> Deserialize<'de> for VirtualMachineType {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s: String = Deserialize::deserialize(deserializer)?;
        VirtualMachineType::from_str(&s).map_err(serde::de::Error::custom)
    }
}

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq, Clone)]
pub struct Body {
    pub name: String,
    pub description: String,
    pub version: String,
    pub authors: Option<Vec<String>>,
    pub license: String,
    pub readme: String,
    pub categories: Option<Vec<String>>,
    pub assets: Option<Vec<Vec<String>>>,
}

impl Body {
    pub fn create_from_toml(toml_path: &Path) -> Result<Body> {
        let deserialized_toml = create_project_from_toml_path(toml_path)?;
        Ok(Body {
            name: deserialized_toml.package.name,
            description: deserialized_toml.package.description,
            version: deserialized_toml.package.version,
            authors: deserialized_toml.package.authors,
            license: deserialized_toml.package.license,
            readme: deserialized_toml.package.readme,
            categories: deserialized_toml.package.categories,
            assets: deserialized_toml.package.assets,
        })
    }
}

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq, Clone)]
pub enum ContentType {
    #[serde(alias = "vm")]
    VM,
    #[serde(alias = "feature", alias = "FEATURE")]
    Feature,
    #[serde(alias = "condition", alias = "CONDITION")]
    Condition,
    #[serde(alias = "inject", alias = "INJECT")]
    Inject,
    #[serde(alias = "event", alias = "EVENT")]
    Event,
    #[serde(alias = "malware", alias = "MALWARE")]
    Malware,
    #[serde(alias = "exercise", alias = "EXERCISE")]
    Exercise,
    #[serde(alias = "banner", alias = "BANNER")]
    Banner,
    #[serde(alias = "other", alias = "OTHER")]
    Other,
}

impl fmt::Display for ContentType {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        match self {
            ContentType::VM => write!(f, "VM"),
            ContentType::Feature => write!(f, "Feature"),
            ContentType::Condition => write!(f, "Condition"),
            ContentType::Inject => write!(f, "Inject"),
            ContentType::Event => write!(f, "Event"),
            ContentType::Malware => write!(f, "Malware"),
            ContentType::Exercise => write!(f, "Exercise"),
            ContentType::Banner => write!(f, "Banner"),
            ContentType::Other => write!(f, "Other"),
        }
    }
}

impl FeatureType {
    pub fn all_variants() -> Vec<&'static str> {
        vec!["service", "configuration", "artifact"]
    }
}

impl ContentType {
    pub fn as_str(&self) -> &str {
        match self {
            ContentType::VM => "VM",
            ContentType::Feature => "Feature",
            ContentType::Condition => "Condition",
            ContentType::Inject => "Inject",
            ContentType::Event => "Event",
            ContentType::Malware => "Malware",
            ContentType::Exercise => "Exercise",
            ContentType::Banner => "Banner",
            ContentType::Other => "Other",
        }
    }
}

impl ContentType {
    pub fn all_variants() -> Vec<&'static str> {
        vec![
            "feature",
            "vm",
            "condition",
            "inject",
            "event",
            "malware",
            "exercise",
            "banner",
            "other",
        ]
    }
}

impl TryFrom<&str> for ContentType {
    type Error = anyhow::Error;

    fn try_from(str: &str) -> Result<Self> {
        match str {
            "vm" => Ok(ContentType::VM),
            "feature" => Ok(ContentType::Feature),
            "condition" => Ok(ContentType::Condition),
            "inject" => Ok(ContentType::Inject),
            "event" => Ok(ContentType::Event),
            "malware" => Ok(ContentType::Malware),
            "exercise" => Ok(ContentType::Exercise),
            "banner" => Ok(ContentType::Banner),
            "other" => Ok(ContentType::Other),
            _ => Err(anyhow!("Invalid content type")),
        }
    }
}

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq, Clone, Hash)]
#[serde(tag = "type", content = "value")]
pub enum Preview {
    #[serde(alias = "picture", alias = "PICTURE")]
    Picture(Vec<String>),
    #[serde(alias = "video", alias = "VIDEO")]
    Video(Vec<String>),
    #[serde(alias = "code", alias = "CODE")]
    Code(Vec<String>),
}

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq, Clone)]
pub struct Content {
    #[serde(rename = "type")]
    pub content_type: ContentType,
    #[serde(alias = "preview", alias = "PREVIEW")]
    pub preview: Option<Vec<Preview>>,
}

impl Content {
    pub fn create_from_toml(toml_path: &Path) -> Result<Content> {
        let deserialized_toml = create_project_from_toml_path(toml_path)?;
        Ok(Content {
            content_type: deserialized_toml.content.content_type,
            preview: deserialized_toml.content.preview,
        })
    }
}
