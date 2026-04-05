use crate::constants::{CONFIGURATION_FILE_RELATIVE_PATH, TOKEN_FILE_RELATIVE_PATH};
use anyhow::Result;
use deputy_library::constants::CONFIGURATION_FOLDER_PATH_ENV_KEY;
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, env, fs::read_to_string, path::PathBuf};

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct Registry {
    pub api: String,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct PackageDownload {
    pub download_path: String,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct Configuration {
    pub registries: HashMap<String, Registry>,
    pub package: PackageDownload,
}

impl Configuration {
    pub fn get_configuration() -> Result<Configuration> {
        let configuration_path: PathBuf = [
            env::var(CONFIGURATION_FOLDER_PATH_ENV_KEY)?,
            CONFIGURATION_FILE_RELATIVE_PATH.to_string(),
        ]
        .iter()
        .collect();
        let configuration_contents = read_to_string(configuration_path)?;
        Ok(toml::from_str(&configuration_contents)?)
    }

    pub fn get_token_file_path() -> Result<PathBuf> {
        let token_file: PathBuf = [
            env::var(CONFIGURATION_FOLDER_PATH_ENV_KEY)?,
            TOKEN_FILE_RELATIVE_PATH.to_string(),
        ]
        .iter()
        .collect();
        Ok(token_file)
    }
}

#[cfg(test)]
mod tests {
    use crate::constants::DEFAULT_REGISTRY_NAME;

    use super::*;
    use anyhow::Result;
    use std::io::Write;
    use tempfile::{tempdir, Builder, NamedTempFile, TempDir};

    fn create_temp_configuration_file() -> Result<(TempDir, NamedTempFile)> {
        let configuration_file_contents = br#"
                [registries]
                main-registry = { api = "apilink" }

                [package]
                download_path = "./download"
                "#;
        let configuration_directory = tempdir()?;
        let mut configuration_file = Builder::new()
            .prefix("configuration")
            .suffix(".toml")
            .rand_bytes(0)
            .tempfile_in(&configuration_directory)?;
        configuration_file.write_all(configuration_file_contents)?;
        Ok((configuration_directory, configuration_file))
    }

    #[test]
    fn read_contents_from_configuration_file() -> Result<()> {
        let (configuration_directory, configuration_file) = create_temp_configuration_file()?;
        env::set_var(
            CONFIGURATION_FOLDER_PATH_ENV_KEY,
            configuration_directory.path(),
        );
        let configuration = Configuration::get_configuration()?;
        env::remove_var(CONFIGURATION_FOLDER_PATH_ENV_KEY);
        assert_eq!(
            configuration
                .registries
                .get(DEFAULT_REGISTRY_NAME)
                .unwrap()
                .api,
            "apilink"
        );
        configuration_file.close()?;
        configuration_directory.close()?;
        Ok(())
    }
}
