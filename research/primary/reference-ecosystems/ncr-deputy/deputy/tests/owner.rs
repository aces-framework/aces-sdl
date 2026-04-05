mod helpers;

#[cfg(test)]
mod tests {
    use crate::helpers::{
        setup_test_backend, upload_test_package, DeployerCLIConfiguration,
        DeployerCLIConfigurationBuilder,
    };
    use anyhow::Result;
    use assert_cmd::Command;
    use deputy_library::constants::CONFIGURATION_FOLDER_PATH_ENV_KEY;

    async fn execute_list_owners_command(
        cli_configuration: &DeployerCLIConfiguration,
        package_name: &str,
    ) -> Result<Vec<String>> {
        let mut command = Command::cargo_bin("deputy")?;
        command.arg("owner").arg("list").arg(package_name);
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );

        command.assert().success();
        let output_string = String::from_utf8(command.output()?.stdout)?;
        let owners = output_string
            .split('\n')
            .filter_map(|entry| match entry.is_empty() {
                true => None,
                false => Some(entry.to_string()),
            })
            .collect::<Vec<String>>();

        Ok(owners)
    }

    #[actix_web::test]
    async fn add_owner() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;

        let mut command = Command::cargo_bin("deputy")?;
        command
            .arg("owner")
            .arg("add")
            .arg("some-user-email")
            .arg("some-package-name");
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );
        command.assert().success();
        let owners = execute_list_owners_command(&cli_configuration, "some-package-name").await?;
        assert!(owners.contains(&"some-user-email".to_string()));

        Ok(())
    }

    #[actix_web::test]
    async fn remove_owner() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;

        let mut command = Command::cargo_bin("deputy")?;
        command
            .arg("owner")
            .arg("add")
            .arg("some-user-email")
            .arg("some-package-name");
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );
        command.assert().success();
        let owners = execute_list_owners_command(&cli_configuration, "some-package-name").await?;
        assert!(owners.contains(&"some-user-email".to_string()));

        let mut command = Command::cargo_bin("deputy")?;
        command
            .arg("owner")
            .arg("remove")
            .arg("some-user-email")
            .arg("some-package-name");
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );
        command.assert().success();
        let owners = execute_list_owners_command(&cli_configuration, "some-package-name").await?;
        assert!(!owners.contains(&"some-user-email".to_string()));

        Ok(())
    }

    #[actix_web::test]
    async fn list_owners() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;

        let owners = execute_list_owners_command(&cli_configuration, "some-package-name").await?;
        assert!(owners.contains(&"test-email".to_string()));

        Ok(())
    }

    #[actix_web::test]
    async fn fails_to_remove_last_owner() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;

        let mut command = Command::cargo_bin("deputy")?;
        command
            .arg("owner")
            .arg("remove")
            .arg("test-email")
            .arg("some-package-name");
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );
        command.assert().failure();
        let output = String::from_utf8(command.output()?.stderr)?;
        assert!(output.contains("Can not remove the last owner of a package"));

        Ok(())
    }
}
