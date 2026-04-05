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

    async fn execute_list_command(
        cli_configuration: &DeployerCLIConfiguration,
        type_filter: Option<&str>,
        category_filter: Option<&str>,
    ) -> Result<String> {
        let mut command = Command::cargo_bin("deputy")?;
        command.arg("list");
        if let Some(type_filter) = type_filter {
            command.arg("--type").arg(type_filter);
        }
        if let Some(category_filter) = category_filter {
            command.arg("--category").arg(category_filter);
        }
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );
        command.assert().success();

        let output_string = String::from_utf8(command.output()?.stdout)?;
        Ok(output_string)
    }

    #[actix_web::test]
    async fn valid_package_list() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;
        let info_response = execute_list_command(&cli_configuration, None, None).await?;
        assert!(info_response.contains(&"some-package-name/VM, 1.0.4".to_string()));
        Ok(())
    }

    #[actix_web::test]
    async fn error_on_package_list_package_not_existing() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        let info_response = execute_list_command(&cli_configuration, None, None).await?;
        assert!(!info_response.contains(&"this-totally-doesnt-exist/VM".to_string()));
        Ok(())
    }

    #[actix_web::test]
    async fn valid_get_package_list_by_type() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;
        let info_response = execute_list_command(&cli_configuration, Some("vm"), None).await?;
        assert!(info_response.contains(&"some-package-name/VM, 1.0.4".to_string()));
        Ok(())
    }

    #[actix_web::test]
    async fn valid_get_package_list_by_single_category() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;
        let info_response =
            execute_list_command(&cli_configuration, None, Some("category1")).await?;
        assert!(info_response.contains(&"some-package-name/VM, 1.0.4".to_string()));
        Ok(())
    }

    #[actix_web::test]
    async fn valid_get_package_list_by_two_categories() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;
        let info_response =
            execute_list_command(&cli_configuration, None, Some("category1,category2")).await?;
        assert!(info_response.contains(&"some-package-name/VM, 1.0.4".to_string()));
        Ok(())
    }

    #[actix_web::test]
    async fn error_on_get_package_list_by_category_not_existing() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;
        let info_response =
            execute_list_command(&cli_configuration, None, Some("this-cat-does-not-exist")).await?;
        assert!(!info_response.contains(&"some-package-name/VM, 1.0.4".to_string()));
        Ok(())
    }

    #[actix_web::test]
    async fn valid_get_package_list_by_type_and_category() -> Result<()> {
        let host = setup_test_backend().await?;
        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;
        upload_test_package(&cli_configuration).await?;
        let info_response =
            execute_list_command(&cli_configuration, Some("Vm"), Some("category2")).await?;
        assert!(info_response.contains(&"some-package-name/VM, 1.0.4".to_string()));
        Ok(())
    }
}
