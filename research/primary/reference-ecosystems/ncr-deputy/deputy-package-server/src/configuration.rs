use anyhow::{Error, Result};
use deputy_library::constants::default_max_archive_size;
use serde::{Deserialize, Serialize};
use std::fs::read_to_string;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Keycloak {
    pub pem_content: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Configuration {
    pub hostname: String,
    pub package_folder: String,
    pub database_url: String,
    pub keycloak: Keycloak,
    #[serde(default = "default_max_archive_size")]
    pub max_archive_size: u64,
}

pub fn read_configuration(arguments: Vec<String>) -> Result<Configuration> {
    let file_path = arguments
        .get(1)
        .ok_or_else(|| Error::msg("Configuration path argument missing"))?;

    let configuration_string = read_to_string(file_path)?;
    Ok(serde_yaml::from_str(&configuration_string)?)
}

#[cfg(test)]
mod tests {
    use super::read_configuration;
    use anyhow::Result;
    use std::fs::File;
    use std::io::Write;
    use tempfile::tempdir;

    #[test]
    fn can_parse_the_configuration() -> Result<()> {
        let temporary_directory = tempdir()?;
        let file_path = temporary_directory.path().join("test-config.yml");
        let path_string = file_path.clone().into_os_string().into_string().unwrap();
        let mut file = File::create(file_path)?;
        writeln!(
            file,
            r#"
hostname: localhost:8080
package_folder: /tmp/packages
database_url: mysql://mysql_user:mysql_pass@deputy-mariadb:3307/deputy
keycloak:
    pem_content: MIICoTCCAYkCBgGFFQ5SLzANBgkqhkiG9w0BAQsFADAUMRIwEAYDVQQDDAl0ZXN0cmVhbG0wHhcNMjIxMjE1MDkxMDM4WhcNMzIxMjE1MDkxMjE4WjAUMRIwEAYDVQQDDAl0ZXN0cmVhbG0wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQC9MCqRfbTMuZzTu6bqaUCNOok6DLV9q6WmCDSpqzByC9u7W7j/MTNwx1tnD1oBrK8zMaS0AXlYT9JGnoAaVVeNjRaPhuOV4hs+Badtfx91E/ZF5nKjeKM3LRcx+Bthmbxlf2sNCBsFOuQafRM/srpYOlbcQ88HKuqDQpWKULUxlMxH2i7rqy9+vGAFAqJJlwtfAMiq3pof08leC8mlBz7QwnlAi6aasFLMJ0KoCBxlYJMAJNWD/CBCAQUu1tBalXVLpw93lZZqurXhw7cLAjKt//4HlkcTrkDDxpMac37GbrNRIbMpIDt//n+mausUfO0ogmQlaJ8a8A/RtBcXGmIXAgMBAAEwDQYJKoZIhvcNAQELBQADggEBADY/bz+lShMF1qB9Vt7oG0BxRiEdMXrf9GzHNL5R1vm7snLKUkfZJgM13/ovQLgWMDyuVFD/AIubWtQPBrFoXQnae/U/YmK7QFoMohBxpf+mHKo21HvxFBTsdaQwSfvFZ0ykFZR+O7huZhbMc/SuhY/cpwRBYtL8CBKORq5At7dz4cPMdf03qyh1wVSkArRz4UyH0T1EKMZU1QW6KgsY8LzGL9lW70UI7EilLKyFzPfpylP/SZP8RLSgy+P/XJYnALXMaWmq+Zom1tuZxjwBxeWr6qv6H1yH7xxLjPJVoF+Mb2zZZQruvzqo9zS0qKOUkVj3WM1resNYpHbmvKAWf8M=
max_archive_size: 1048576
    "#
        )?;
        let arguments = vec![String::from("program-name"), path_string];
        let configuration = read_configuration(arguments)?;
        insta::assert_debug_snapshot!(configuration);
        Ok(())
    }
}
