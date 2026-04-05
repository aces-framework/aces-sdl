mod helpers;

#[cfg(test)]
mod tests {
    use crate::helpers::DeployerCLIConfigurationBuilder;
    use anyhow::Result;
    use assert_cmd::prelude::*;
    use deputy_library::constants::CONFIGURATION_FOLDER_PATH_ENV_KEY;
    use predicates::prelude::*;
    use std::{env, process::Command};

    #[test]
    fn test_version() -> Result<()> {
        let mut command = Command::cargo_bin("deputy")?;
        let configuration = DeployerCLIConfigurationBuilder::builder().build()?;

        command.arg("--version");
        command.env(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            configuration.configuration_folder.path(),
        );
        command
            .assert()
            .success()
            .stdout(predicate::str::contains(env!("CARGO_PKG_VERSION")));

        Ok(())
    }
}
