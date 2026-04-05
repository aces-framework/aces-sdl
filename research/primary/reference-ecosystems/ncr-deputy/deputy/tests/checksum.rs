mod helpers;

#[cfg(test)]
mod tests {
    use crate::helpers::{login, publish_package, DeployerCLIConfigurationBuilder};
    use anyhow::Result;
    use assert_cmd::Command;
    use deputy_library::{
        constants::CONFIGURATION_FOLDER_PATH_ENV_KEY, package::Package, test::TempArchive,
    };
    use deputy_package_server::test::TestPackageServerBuilder;
    use std::{
        fs::remove_dir_all,
        path::PathBuf,
        thread::{self, JoinHandle},
    };
    use tempfile::TempDir;

    fn spawn_checksum_request(
        config_path: PathBuf,
        temp_dir: PathBuf,
        local_checksum: String,
    ) -> JoinHandle<Result<(), anyhow::Error>> {
        thread::spawn(move || {
            let mut command = Command::cargo_bin("deputy")?;
            command.arg("checksum").arg("some-package-name");
            command.current_dir(temp_dir);
            command.env(CONFIGURATION_FOLDER_PATH_ENV_KEY, config_path);
            command.assert().success();
            command.assert().stdout(format!("{local_checksum}\n"));
            Ok::<_, anyhow::Error>(())
        })
    }

    #[actix_web::test]
    async fn create_concurrent_checksum_requests() -> Result<()> {
        let temp_dir = TempDir::new()?.into_path();
        let temp_project = TempArchive::builder()
            .set_package_name("some-package-name")
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
        let mut package: Package = (&temp_project).try_into()?;
        let local_checksum = package.file.calculate_checksum()?;

        const CONCURRENT_REQUESTS: usize = 10;
        let requests = vec![0; CONCURRENT_REQUESTS];
        let join_handles = requests.iter().map(|_| {
            spawn_checksum_request(
                cli_configuration.configuration_folder.path().to_path_buf(),
                temp_dir.clone(),
                local_checksum.clone(),
            )
        });

        for handle in join_handles {
            handle.join().unwrap()?;
        }
        Ok(())
    }

    #[actix_web::test]
    async fn get_package_checksum() -> Result<()> {
        let temp_dir = TempDir::new()?.into_path();
        let temp_project = TempArchive::builder()
            .set_package_name("some-package-name")
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
        let mut package: Package = (&temp_project).try_into()?;
        let local_checksum = package.file.calculate_checksum()?;

        let mut command = Command::cargo_bin("deputy")?;
        command.arg("checksum").arg("some-package-name");
        command.current_dir(&temp_dir);
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            cli_configuration.configuration_folder.path(),
        );
        command.assert().success();
        command.assert().stdout(format!("{local_checksum}\n"));
        remove_dir_all(temp_dir.as_path())?;

        Ok(())
    }
}
