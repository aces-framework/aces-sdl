mod helpers;

#[cfg(test)]
mod tests {
    use crate::helpers::DeployerCLIConfigurationBuilder;
    use anyhow::Result;
    use assert_cmd::Command;
    use deputy_library::{constants::CONFIGURATION_FOLDER_PATH_ENV_KEY, test::TempArchive};
    use deputy_package_server::test::TestPackageServerBuilder;
    use predicates::prelude::{predicate, PredicateBooleanExt};

    #[actix_web::test]
    async fn valid_package_received_and_verified() -> Result<()> {
        let temp_project = TempArchive::builder().build()?;

        let mut command = Command::cargo_bin("deputy")?;
        command.arg("inspect");
        command.current_dir(temp_project.root_dir.path());

        let test_backend = TestPackageServerBuilder::try_new()?;
        let host = test_backend.get_host().to_string();
        let test_backend = test_backend.build();
        test_backend.start().await?;

        let deputy_configuration = DeployerCLIConfigurationBuilder::builder()
            .host(&host)
            .build()?;

        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            deputy_configuration.configuration_folder.path(),
        );

        command.assert().success();

        command
            .assert()
            .stdout(predicate::str::contains("Warning").not());
        Ok(())
    }
}
