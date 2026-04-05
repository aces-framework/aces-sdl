mod helpers;

#[cfg(test)]
mod tests {
    use crate::helpers::{login, publish_package, DeployerCLIConfigurationBuilder};
    use anyhow::Result;
    use assert_cmd::Command;
    use deputy_library::{constants::CONFIGURATION_FOLDER_PATH_ENV_KEY, test::TempArchive};
    use deputy_package_server::test::TestPackageServerBuilder;
    use tempfile::TempDir;

    #[actix_web::test]
    async fn downloads_package() -> Result<()> {
        let temp_dir = TempDir::new()?.into_path();
        let temp_project = TempArchive::builder()
            .set_package_name("some-package-name")
            .set_package_version("0.1.0")
            .build()?;
        let root_dir = temp_project.root_dir.as_ref();
        let test_backend = TestPackageServerBuilder::try_new()?;

        let host = test_backend.get_host();
        let test_backend = test_backend.build();
        test_backend.start().await?;

        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(host)
            .build()?;

        login(
            cli_configuration.configuration_folder.path(),
            "some-token-value",
        )?;
        publish_package(root_dir, cli_configuration.configuration_folder.path())?;

        let mut command = Command::cargo_bin("deputy")?;
        command.arg("fetch").arg("some-package-name");
        command.current_dir(&temp_dir);
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );
        command.assert().success();

        assert!(&temp_dir.as_path().join("some-package-name-0.1.0").exists());
        Ok(())
    }

    #[actix_web::test]
    async fn downloads_package_is_case_insensitive() -> Result<()> {
        let temp_dir = TempDir::new()?.into_path();
        let temp_project = TempArchive::builder()
            .set_package_name("SOME-package-name")
            .set_package_version("0.1.0")
            .build()?;
        let root_dir = temp_project.root_dir.as_ref();
        let test_backend = TestPackageServerBuilder::try_new()?;

        let host = test_backend.get_host();
        let test_backend = test_backend.build();
        test_backend.start().await?;

        let cli_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(host)
            .build()?;

        login(
            cli_configuration.configuration_folder.path(),
            "some-token-value",
        )?;
        publish_package(root_dir, cli_configuration.configuration_folder.path())?;

        let mut command = Command::cargo_bin("deputy")?;
        command.arg("fetch").arg("some-package-NAME");
        command.current_dir(&temp_dir);
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );
        command.assert().success();

        assert!(&temp_dir.as_path().join("some-package-NAME-0.1.0").exists());
        Ok(())
    }
}
