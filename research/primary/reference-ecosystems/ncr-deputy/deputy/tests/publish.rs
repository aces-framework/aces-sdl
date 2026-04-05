mod helpers;

#[cfg(test)]
mod tests {
    use std::{fs, path::PathBuf};

    use crate::helpers::{login, DeployerCLIConfigurationBuilder};
    use anyhow::Result;
    use assert_cmd::Command;
    use deputy_library::{
        constants::CONFIGURATION_FOLDER_PATH_ENV_KEY, package::Package, test::TempArchive,
    };
    use deputy_package_server::test::TestPackageServerBuilder;
    use predicates::prelude::predicate;
    use tempfile::{Builder, TempDir};

    #[actix_web::test]
    async fn valid_small_package_was_sent_and_received() -> Result<()> {
        let temp_project = TempArchive::builder().build()?;
        let toml_path = temp_project.toml_file.path().to_path_buf();

        let mut command = Command::cargo_bin("deputy")?;
        command.arg("publish");
        command.current_dir(temp_project.root_dir.path());

        let test_backend = TestPackageServerBuilder::try_new()?;

        let host = test_backend.get_host();
        let package_folder = test_backend.get_package_folder();
        let test_backend = test_backend.build();
        test_backend.start().await?;

        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(host)
            .build()?;
        login(
            cli_configuration.configuration_folder.path(),
            "some-token-value",
        )?;

        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );

        let temp_package = Package::from_file(&toml_path, 0)?;
        let outbound_package_size = &temp_package.file.metadata().unwrap().len();
        let saved_package_path: PathBuf = [
            package_folder,
            &temp_package.metadata.name,
            &temp_package.metadata.version,
        ]
        .iter()
        .collect();

        command.assert().success();

        let saved_package_size: u64 = fs::metadata(saved_package_path)?.len();
        assert_eq!(outbound_package_size, &saved_package_size);

        temp_project.root_dir.close()?;

        Ok(())
    }

    #[actix_web::test]
    async fn valid_large_package_was_sent_and_received() -> Result<()> {
        let temp_project = TempArchive::builder().is_large(true).build()?;
        let toml_path = temp_project.toml_file.path().to_path_buf();
        let mut command = Command::cargo_bin("deputy")?;
        command.arg("publish");
        command.current_dir(temp_project.root_dir.path());

        let test_backend = TestPackageServerBuilder::try_new()?;

        let host = test_backend.get_host();
        let package_folder = test_backend.get_package_folder();
        let test_backend = test_backend.build();
        test_backend.start().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(host)
            .build()?;

        login(
            cli_configuration.configuration_folder.path(),
            "some-token-value",
        )?;
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );

        let temp_package = Package::from_file(&toml_path, 0)?;
        let outbound_package_size = &temp_package.file.metadata().unwrap().len();
        let saved_package_path: PathBuf = [
            package_folder,
            &temp_package.metadata.name,
            &temp_package.metadata.version,
        ]
        .iter()
        .collect();

        command.assert().success();
        let saved_package_size = fs::metadata(saved_package_path)?.len();
        assert_eq!(outbound_package_size, &saved_package_size);

        temp_project.root_dir.close()?;
        Ok(())
    }

    #[actix_web::test]
    async fn error_on_missing_package_toml_file() -> Result<()> {
        let temp_dir = TempDir::new()?;
        let temp_dir = temp_dir.into_path().canonicalize()?;

        let test_backend = TestPackageServerBuilder::try_new()?;
        let host = test_backend.get_host().to_string();
        let test_backend = test_backend.build();
        test_backend.start().await?;

        let deputy_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;

        let mut command = Command::cargo_bin("deputy")?;
        command.arg("publish");
        command.current_dir(temp_dir);
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            deputy_configuration.configuration_folder.path(),
        );
        command.assert().failure().stderr(predicate::str::contains(
            "Error: Could not find package.toml",
        ));

        Ok(())
    }

    #[actix_web::test]
    async fn error_on_missing_package_toml_content() -> Result<()> {
        let temp_dir = TempDir::new()?;

        let test_backend = TestPackageServerBuilder::try_new()?;
        let host = test_backend.get_host().to_string();
        let test_backend = test_backend.build();
        test_backend.start().await?;

        let deputy_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;

        let _package_toml = Builder::new()
            .prefix("package")
            .suffix(".toml")
            .rand_bytes(0)
            .tempfile_in(&temp_dir)?;
        let temp_dir = temp_dir.into_path().canonicalize()?;

        let mut command = Command::cargo_bin("deputy")?;
        command.arg("publish");
        command.current_dir(temp_dir);
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            deputy_configuration.configuration_folder.path(),
        );
        command.assert().failure().stderr(predicate::str::contains(
            "Error: TOML parse error at line 1, column 1",
        ));

        Ok(())
    }

    #[actix_web::test]
    async fn valid_small_package_was_sent_and_received_with_non_default_registry() -> Result<()> {
        let temp_project = TempArchive::builder().build()?;
        let toml_path = temp_project.toml_file.path().to_path_buf();
        let registry_name = String::from("other-registry");

        let test_backend = TestPackageServerBuilder::try_new()?;
        let host = test_backend.get_host().to_string();
        let package_folder = test_backend.get_package_folder();
        let test_backend = test_backend.build();
        test_backend.start().await?;

        let deputy_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .registry_name(&registry_name)
            .build()?;
        let mut login_command = Command::cargo_bin("deputy")?;
        login_command
            .arg("login")
            .arg("--token")
            .arg("some-token-value")
            .arg("--registry-name")
            .arg(&registry_name);
        login_command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            deputy_configuration.configuration_folder.path(),
        );
        login_command.assert().success();

        let mut command = Command::cargo_bin("deputy")?;
        command
            .arg("publish")
            .arg("--registry-name")
            .arg(&registry_name);
        command.current_dir(temp_project.root_dir.path());

        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            deputy_configuration.configuration_folder.path(),
        );

        let temp_package = Package::from_file(&toml_path, 0)?;
        let outbound_package_size = &temp_package.file.metadata().unwrap().len();
        let saved_package_path: PathBuf = [
            package_folder,
            &temp_package.metadata.name,
            &temp_package.metadata.version,
        ]
        .iter()
        .collect();

        command.assert().success();
        let saved_package_size = fs::metadata(saved_package_path)?.len();
        assert_eq!(outbound_package_size, &saved_package_size);

        temp_project.root_dir.close()?;
        Ok(())
    }

    #[actix_web::test]
    async fn error_on_invalid_compression_level() -> Result<()> {
        let temp_project = TempArchive::builder().build()?;

        let test_backend = TestPackageServerBuilder::try_new()?;
        let host = test_backend.get_host().to_string();
        let test_backend = test_backend.build();
        test_backend.start().await?;

        let deputy_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        let mut login_command = Command::cargo_bin("deputy")?;
        login_command
            .arg("login")
            .arg("--token")
            .arg("some-token-value");
        login_command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            deputy_configuration.configuration_folder.path(),
        );
        login_command.assert().success();

        let mut command = Command::cargo_bin("deputy")?;
        command.current_dir(temp_project.root_dir.path());
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            deputy_configuration.configuration_folder.path(),
        );

        command.arg("publish").arg("--compression").arg(&"100");
        command.assert().failure().stderr(predicate::str::contains(
            "invalid value '100' for '--compression <COMPRESSION>': 100 is not in 0..=9",
        ));

        temp_project.root_dir.close()?;
        Ok(())
    }
}
