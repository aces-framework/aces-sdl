use std::fmt::Debug;
use std::fs::File;
use std::io::Read;
use std::path::Path;

use crate::package::PackageMetadata;
use crate::{
    constants::{self},
    package::Package,
    project::*,
};
use anyhow::{anyhow, Result};
use constants::{MAX_NAME_LENGTH, MIN_NAME_LENGTH};
use semver::VersionReq;
use spdx;

pub trait Validate {
    fn validate(&mut self) -> Result<()>;
}

pub trait ValidatePackage {
    fn validate(&mut self, max_archive_size: u64) -> Result<()>;
}

impl ValidatePackage for Package {
    fn validate(&mut self, max_archive_size: u64) -> Result<()> {
        self.metadata.validate()?;
        self.validate_consistency()?;
        self.validate_file_type()?;
        self.validate_archive_size(max_archive_size)?;
        self.validate_checksum()?;
        Ok(())
    }
}

impl Validate for PackageMetadata {
    fn validate(&mut self) -> Result<()> {
        validate_name(self.name.clone())?;
        validate_version_semantic(self.version.clone())?;
        validate_license(self.license.clone())?;
        validate_categories(self.categories.clone())?;

        if self.checksum.is_empty() {
            return Err(anyhow!("Package checksum is empty"));
        }
        if self.checksum.len() != constants::SHA256_LENGTH
            || !self.checksum.chars().all(|c| c.is_ascii_hexdigit())
        {
            return Err(anyhow!("Package checksum is not valid"));
        }
        Ok(())
    }
}

impl Validate for Project {
    fn validate(&mut self) -> Result<()> {
        self.validate_content()?;
        validate_name(self.package.name.clone())?;
        validate_version_semantic(self.package.version.clone())?;
        validate_license(self.package.license.clone())?;
        validate_categories(self.package.categories.clone())?;
        self.validate_assets()?;
        Ok(())
    }
}

pub fn validate_name(name: String) -> Result<()> {
    if !constants::VALID_NAME.is_match(&name)? {
        return Err(anyhow!(
            "Name {:?} must be one word of alphanumeric, `-`, or `_` characters.",
            name
        ));
    };
    if name.len() > MAX_NAME_LENGTH || name.len() < MIN_NAME_LENGTH {
        return Err(anyhow!(
            "Package name must be between {MIN_NAME_LENGTH} and {MAX_NAME_LENGTH} characters long."
        ));
    }
    Ok(())
}

pub fn validate_version_semantic(version: String) -> Result<()> {
    match VersionReq::parse(version.as_str()) {
        Ok(_) => Ok(()),
        Err(_) => Err(anyhow!(
            "Version {:?} must match Semantic Versioning 2.0.0 https://semver.org/",
            version
        )),
    }
}

pub fn validate_license(license: String) -> Result<()> {
    match spdx::license_id(&license) {
        Some(_) => Ok(()),
        None => Err(anyhow!(
            "License must match SPDX specifications https://spdx.dev/spdx-specification-21-web-version/#h.jxpfx0ykyb60"
        )),
    }
}

pub fn validate_categories(categories: Option<Vec<String>>) -> Result<()> {
    if let Some(categories) = categories {
        for category in categories.iter() {
            if category.trim().is_empty() {
                return Err(anyhow!(
                    "A category cannot be an empty string or only whitespace"
                ));
            }
        }
    }
    Ok(())
}

pub fn validate_package_toml<P: AsRef<Path> + Debug>(package_path: P) -> Result<()> {
    let mut file = File::open(package_path)?;
    let mut contents = String::new();
    file.read_to_string(&mut contents)?;

    let mut deserialized_toml: Project = toml::from_str(&contents)?;
    deserialized_toml.validate()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        project::enums::{Architecture, OperatingSystem},
        test::{TEST_INVALID_PACKAGE_TOML_SCHEMA, TEST_VALID_PACKAGE_TOML_SCHEMA},
    };

    use anyhow::Ok;
    use std::io::Write;
    use tempfile::{Builder, NamedTempFile};

    fn create_temp_file(toml_content: &[u8]) -> Result<(NamedTempFile, Project)> {
        let mut file = Builder::new()
            .prefix("package")
            .suffix(".toml")
            .tempfile()?;
        file.write_all(toml_content)?;
        let deserialized_toml = deserialize_toml(&file)?;
        Ok((file, deserialized_toml))
    }

    fn deserialize_toml(file: &NamedTempFile) -> Result<Project> {
        let mut contents = String::new();
        let mut read_file = File::open(file.path())?;
        read_file.read_to_string(&mut contents)?;
        let deserialized_toml: Project = toml::from_str(&contents)?;
        Ok(deserialized_toml)
    }

    fn create_incorrect_name_version_license_toml() -> Result<(NamedTempFile, Project)> {
        let toml_content = br#"
            [package]
            name = "this is incorrect formatting"
            description = "description"
            version = "version 23"
            license = "Very bad licence"
            readme = "readme.md"
            [content]
            type = "vm"
            "#;
        let (file, deserialized_toml) = create_temp_file(toml_content)?;
        Ok((file, deserialized_toml))
    }

    #[test]
    fn positive_result_all_fields_correct() -> Result<()> {
        let (file, _deserialized_toml) =
            create_temp_file(TEST_VALID_PACKAGE_TOML_SCHEMA.as_bytes())?;
        assert!(validate_package_toml(file.path()).is_ok());
        file.close()?;
        Ok(())
    }

    #[test]
    fn negative_result_name_field() -> Result<()> {
        let (file, deserialized_toml) = create_incorrect_name_version_license_toml()?;
        assert!(validate_name(deserialized_toml.package.name).is_err());
        file.close()?;
        Ok(())
    }

    #[test]
    fn negative_result_version_field() -> Result<()> {
        let (file, deserialized_toml) = create_incorrect_name_version_license_toml()?;
        assert!(validate_version_semantic(deserialized_toml.package.version).is_err());
        file.close()?;
        Ok(())
    }

    #[test]
    fn negative_result_license_field() -> Result<()> {
        let (file, deserialized_toml) = create_incorrect_name_version_license_toml()?;
        assert!(validate_license(deserialized_toml.package.license).is_err());
        file.close()?;
        Ok(())
    }

    #[test]
    fn missing_architecture_field_is_given_value_none() -> Result<()> {
        let (file, deserialized_toml) =
            create_temp_file(TEST_INVALID_PACKAGE_TOML_SCHEMA.as_bytes())?;
        if let Some(virtual_machine) = &deserialized_toml.virtual_machine {
            assert!(virtual_machine.architecture.is_none());
        }
        file.close()?;
        Ok(())
    }

    #[test]
    fn invalid_operating_system_field_is_given_value_unknown() -> Result<()> {
        let (file, deserialized_toml) =
            create_temp_file(TEST_INVALID_PACKAGE_TOML_SCHEMA.as_bytes())?;
        if let Some(virtual_machine) = deserialized_toml.virtual_machine {
            if let Some(operating_system) = virtual_machine.operating_system {
                assert_eq!(operating_system, OperatingSystem::Unknown);
            }
        }
        file.close()?;
        Ok(())
    }

    #[test]
    fn valid_operating_system_and_architecture_fields_are_parsed_correctly() -> Result<()> {
        let (file, deserialized_toml) =
            create_temp_file(TEST_VALID_PACKAGE_TOML_SCHEMA.as_bytes())?;
        if let Some(virtual_machine) = deserialized_toml.virtual_machine {
            if let Some(operating_system) = virtual_machine.operating_system {
                assert_eq!(operating_system, OperatingSystem::Debian);
            }
            if let Some(architecture) = virtual_machine.architecture {
                assert_eq!(architecture, Architecture::arm64);
            }
        }
        file.close()?;
        Ok(())
    }

    #[test]
    fn feature_type_package_is_parsed_and_passes_validation() -> Result<()> {
        let toml_content = br#"
            [package]
            name = "my-cool-feature"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            assets = [
                ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "744"],
                ["src/configs/my-cool-config2.yml", "/var/opt/my-cool-service2", "777"],
                ["src/configs/my-cool-config3.yml", "/var/opt/my-cool-service3"],
                ]
            [content]
            type = "feature"
            [feature]
            type = "configuration"
            action = "ping 8.8.8.8"
            "#;
        let (file, project) = create_temp_file(toml_content)?;

        assert!(validate_package_toml(file.path()).is_ok());
        insta::with_settings!({sort_maps => true}, {
                insta::assert_toml_snapshot!(project);
        });

        file.close()?;
        Ok(())
    }

    #[test]
    fn inject_type_package_is_parsed_and_passes_validation() -> Result<()> {
        let toml_content = br#"
            [package]
            name = "my-cool-feature"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            assets = [
                ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "744"],
                ["src/configs/my-cool-config2.yml", "/var/opt/my-cool-service2", "777"],
                ["src/configs/my-cool-config3.yml", "/var/opt/my-cool-service3"],
                ]
            [content]
            type = "inject"
            [inject]
            action = "ping 8.8.8.8"
            "#;
        let (file, project) = create_temp_file(toml_content)?;

        assert!(validate_package_toml(file.path()).is_ok());
        insta::with_settings!({sort_maps => true}, {
                insta::assert_toml_snapshot!(project);
        });

        file.close()?;
        Ok(())
    }

    #[test]
    fn condition_type_package_is_parsed_and_passes_validation() -> Result<()> {
        let toml_content = br#"
            [package]
            name = "my-cool-condition"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            assets = [
                ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "744"],
                ["src/configs/my-cool-config2.yml", "/var/opt/my-cool-service2", "777"],
                ["src/configs/my-cool-config3.yml", "/var/opt/my-cool-service3"],
                ]
            [content]
            type = "condition"
            [condition]
            action = "executable/path.sh"
            interval = 30
            "#;
        let (file, project) = create_temp_file(toml_content)?;

        validate_package_toml(file.path())?;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_toml_snapshot!(project);
        });

        file.close()?;
        Ok(())
    }

    #[test]
    fn event_type_package_is_parsed_and_passes_validation() -> Result<()> {
        let toml_content = br#"
            [package]
            name = "my-cool-condition"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            assets = [
                ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "744"],
                ["src/configs/my-cool-config2.yml", "/var/opt/my-cool-service2", "777"],
                ["src/configs/my-cool-config3.yml", "/var/opt/my-cool-service3"],
                ]
            [content]
            type = "event"
            [event]
            file_path = "info.md"
            "#;
        let (file, project) = create_temp_file(toml_content)?;

        validate_package_toml(file.path())?;
        insta::with_settings!({sort_maps => true}, {
                insta::assert_toml_snapshot!(project);
        });

        file.close()?;
        Ok(())
    }

    #[test]
    fn malware_type_package_is_parsed_and_passes_validation() -> Result<()> {
        let toml_content = br#"
            [package]
            name = "my-cool-condition"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            assets = [
                ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "744"],
                ["src/configs/my-cool-config2.yml", "/var/opt/my-cool-service2", "777"],
                ["src/configs/my-cool-config3.yml", "/var/opt/my-cool-service3"],
                ]
            [content]
            type = "malware"
            [malware]
            action = "installer/install_something.sh"
            "#;
        let (file, project) = create_temp_file(toml_content)?;

        assert!(validate_package_toml(file.path()).is_ok());
        insta::with_settings!({sort_maps => true}, {
                insta::assert_toml_snapshot!(project);
        });

        file.close()?;
        Ok(())
    }

    #[test]
    fn exercise_type_package_is_parsed_and_passes_validation() -> Result<()> {
        let toml_content = br#"
            [package]
            name = "my-cool-condition"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            [content]
            type = "exercise"
            [exercise]
            file_path = "exercise.yml"
            "#;
        let (file, project) = create_temp_file(toml_content)?;

        assert!(validate_package_toml(file.path()).is_ok());
        insta::with_settings!({sort_maps => true}, {
                insta::assert_toml_snapshot!(project);
        });

        file.close()?;
        Ok(())
    }

    #[test]
    fn banner_type_package_is_parsed_and_passes_validation() -> Result<()> {
        let toml_content = br#"
            [package]
            name = "my-cool-condition"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            [content]
            type = "banner"
            [banner]
            file_path = "banner.md"
            "#;
        let (file, project) = create_temp_file(toml_content)?;

        assert!(validate_package_toml(file.path()).is_ok());
        insta::with_settings!({sort_maps => true}, {
                insta::assert_toml_snapshot!(project);
        });

        file.close()?;
        Ok(())
    }

    #[test]
    fn other_type_package_is_parsed_and_passes_validation() -> Result<()> {
        let toml_content = br#"
            [package]
            name = "my-cool-condition"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            [content]
            type = "other"
            [other]
            random_field = "hello"
            "#;
        let (file, project) = create_temp_file(toml_content)?;

        assert!(validate_package_toml(file.path()).is_ok());
        insta::with_settings!({sort_maps => true}, {
                insta::assert_toml_snapshot!(project);
        });

        file.close()?;
        Ok(())
    }

    #[test]
    #[should_panic(expected = "Feature package info not found")]
    fn negative_result_on_content_type_not_matching_content() {
        let toml_content = br#"
            [package]
            name = "my-cool-condition"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            assets = [
                ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "744"],
                ["src/configs/my-cool-config2.yml", "/var/opt/my-cool-service2", "777"],
                ["src/configs/my-cool-config3.yml", "/var/opt/my-cool-service3"],
                ]
            [content]
            type = "feature"
            [condition]
            action = "executable/path.sh"
            interval = 30
            "#;
        let (file, _) = create_temp_file(toml_content).unwrap();
        validate_package_toml(file.path()).unwrap();
        file.close().unwrap();
    }

    #[test]
    #[should_panic(expected = "Multiple content types per package are not supported")]
    fn negative_result_on_multiple_contents() {
        let toml_content = br#"
            [package]
            name = "my-cool-condition"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            assets = [
                ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "744"],
                ["src/configs/my-cool-config2.yml", "/var/opt/my-cool-service2", "777"],
                ["src/configs/my-cool-config3.yml", "/var/opt/my-cool-service3"],
                ]
            [content]
            type = "feature"
            [feature]
            type = "configuration"
            action = "ping 8.8.8.8"
            [condition]
            action = "executable/path.sh"
            interval = 30
            "#;
        let (file, _) = create_temp_file(toml_content).unwrap();
        validate_package_toml(file.path()).unwrap();
        file.close().unwrap();
    }

    #[test]
    #[should_panic(expected = "Package.assets[0][2] is invalid.")]
    fn negative_result_on_invalid_asset_permissions() {
        let toml_content = br#"
            [package]
            name = "my-cool-condition"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            assets = [
                ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "999"],
                ["src/configs/my-cool-config2.yml", "/var/opt/my-cool-service2", "hello"],
                ["src/configs/my-cool-config3.yml", "/var/opt/my-cool-service3"],
                ]
            [content]
            type = "malware"
            [malware]
            action = "installer/install_something.sh"
            "#;
        let (file, _) = create_temp_file(toml_content).unwrap();
        println!("{:?}", validate_package_toml(file.path()).unwrap());
        file.close().unwrap();
    }

    #[test]
    fn restarts_field_is_assigned_default_value() -> Result<()> {
        let toml_content = br#"
            [package]
            name = "my-restarting-feature"
            description = "description"
            version = "1.0.0"
            license = "Apache-2.0"
            readme = "readme.md"
            assets = [
                ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "744"],
                ]
            [content]
            type = "feature"
            [feature]
            type = "service"
            action = "installer/install_something.sh"
            "#;
        let (file, project) = create_temp_file(toml_content)?;

        assert!(validate_package_toml(file.path()).is_ok());
        assert_eq!(project.feature.unwrap().restarts, false);

        file.close()?;
        Ok(())
    }

    #[test]
    fn delete_action_is_assigned_default_value() -> Result<()> {
        let toml_content = br#"
        [package]
        name = "my-restarting-feature"
        description = "description"
        version = "1.0.0"
        license = "Apache-2.0"
        readme = "readme.md"
        assets = [
            ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "744"],
            ]
        [content]
        type = "feature"
        [feature]
        type = "service"
        action = "installer/install_something.sh"
        "#;
        let (file, project) = create_temp_file(toml_content)?;

        assert!(validate_package_toml(file.path()).is_ok());
        assert_eq!(project.feature.unwrap().delete_action, None);

        file.close()?;
        Ok(())
    }

    #[test]
    fn delete_action_is_assigned_value() -> Result<()> {
        let toml_content = br#"
        [package]
        name = "my-restarting-feature"
        description = "description"
        version = "1.0.0"
        license = "Apache-2.0"
        readme = "readme.md"
        assets = [
            ["src/configs/my-cool-config1.yml", "/var/opt/my-cool-service1", "744"],
            ]
        [content]
        type = "feature"
        [feature]
        type = "service"
        delete = "delete.sh"
        "#;
        let (file, project) = create_temp_file(toml_content)?;

        assert!(validate_package_toml(file.path()).is_ok());
        assert_eq!(
            project.feature.unwrap().delete_action,
            Some("delete.sh".to_string())
        );

        file.close()?;
        Ok(())
    }
}
