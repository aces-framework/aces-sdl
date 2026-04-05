#![allow(dead_code)]

use anyhow::Result;
use assert_cmd::Command;
use deputy::constants::DEFAULT_REGISTRY_NAME;
use deputy_library::{constants::CONFIGURATION_FOLDER_PATH_ENV_KEY, test::TempArchive};
use deputy_package_server::test::TestPackageServerBuilder;
use std::{io::Write, path::Path};
use tempfile::{tempdir, Builder, NamedTempFile, TempDir};

pub fn login(configuration_folder: &Path, token_value: &str) -> Result<()> {
    let mut command = Command::cargo_bin("deputy")?;
    command.arg("login");
    command.env(CONFIGURATION_FOLDER_PATH_ENV_KEY, configuration_folder);
    command.arg("--token");
    command.arg(token_value);
    command.assert().success();
    Ok(())
}

pub fn publish_package(package_folder: &Path, configuration_folder: &Path) -> Result<()> {
    let mut command = Command::cargo_bin("deputy")?;
    command.arg("publish");
    command.current_dir(package_folder);

    command.env(CONFIGURATION_FOLDER_PATH_ENV_KEY, configuration_folder);
    command.assert().success();

    Ok(())
}

pub struct DeployerCLIConfigurationBuilder {
    registry_name: String,
    api_address: String,
}

pub struct DeployerCLIConfiguration {
    pub configuration_folder: TempDir,
    pub configuration_file: NamedTempFile,
}

impl DeployerCLIConfigurationBuilder {
    pub fn builder() -> Self {
        Self {
            registry_name: DEFAULT_REGISTRY_NAME.to_string(),
            api_address: "http://localhost:8080/".to_string(),
        }
    }

    pub fn registry_name(mut self, registry_name: &str) -> Self {
        self.registry_name = registry_name.to_string();
        self
    }

    pub fn host(mut self, host: &str) -> Self {
        self.api_address = format!("http://{}/", host);
        self
    }

    pub fn build(self) -> Result<DeployerCLIConfiguration> {
        let configuration_file_contents = format!(
            "[registries]\n{} = {{ api = \"{}\" }}\n[package]\ndownload_path = \"./download\"",
            self.registry_name, self.api_address
        );

        let configuration_folder = tempdir()?;
        let mut configuration_file = Builder::new()
            .prefix("configuration")
            .suffix(".toml")
            .rand_bytes(0)
            .tempfile_in(&configuration_folder)?;
        configuration_file.write_all(configuration_file_contents.as_bytes())?;
        Ok(DeployerCLIConfiguration {
            configuration_folder,
            configuration_file,
        })
    }
}

pub async fn setup_test_backend() -> Result<String> {
    let test_backend = TestPackageServerBuilder::try_new()?;
    let host = test_backend.get_host();
    let test_backend = test_backend.build();
    test_backend.start().await?;
    Ok(host.to_string())
}

pub async fn upload_test_package(cli_configuration: &DeployerCLIConfiguration) -> Result<()> {
    let temp_project = TempArchive::builder()
        .set_package_name("some-package-name")
        .build()?;
    let root_dir = temp_project.root_dir.as_ref();

    login(
        cli_configuration.configuration_folder.path(),
        "some-token-value",
    )?;
    publish_package(root_dir, cli_configuration.configuration_folder.path())?;
    Ok(())
}
