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

    async fn execute_info_command(
        cli_configuration: &DeployerCLIConfiguration,
        search_term: &str,
    ) -> Result<String> {
        let mut command = Command::cargo_bin("deputy")?;
        command.arg("info").arg(search_term);
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );
        command.assert().success();

        let output_string = String::from_utf8(command.output()?.stdout)?;
        Ok(output_string)
    }

    #[actix_web::test]
    async fn valid_get_package_info() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;
        let info_response = execute_info_command(&cli_configuration, "some-package-name").await?;
        assert!(info_response.contains(&"Name: some-package-name".to_string()));
        Ok(())
    }

    #[actix_web::test]
    async fn error_on_package_info_package_not_existing() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        let info_response = execute_info_command(&cli_configuration, "this-does-not-exist").await?;
        assert!(info_response.contains(&"Error: Package not found".to_string()));
        Ok(())
    }
}
