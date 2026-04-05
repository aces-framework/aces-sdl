use crate::client::Client;
use crate::commands::{
    ChecksumOptions, CreateOptions, FetchOptions, InfoOptions, InspectOptions, ListOptions,
    LoginOptions, NormalizeVersionOptions, OwnerOptions, PublishOptions, YankOptions,
};
use crate::configuration::Configuration;
use crate::helpers::{
    banner_fields, condition_fields, create_default_readme, create_temporary_package_download_path,
    event_fields, exercise_fields, feature_fields, find_toml, get_download_target_name,
    inject_fields, malware_fields, other_fields, print_latest_version_package_list_entry,
    print_package_info, print_package_list_entry, set_assets_field, unpack_package_file,
    virtual_machine_fields,
};
use crate::progressbar::{AdvanceProgressBar, ProgressStatus, SpinnerProgressBar};
use actix::Actor;
use anyhow::{anyhow, Ok, Result};
use colored::Colorize;
use deputy_library::constants::ASSETS_REQUIRED_PACKAGE_TYPES;
use deputy_library::project::ContentType;
use deputy_library::rest::{PackageWithVersionsRest, VersionRest};
use deputy_library::validation::{validate_license, Validate};
use deputy_library::{package::Package, project::create_project_from_toml_path};
use dialoguer::{Input, Select};
use std::env::current_dir;
use std::fs;
use std::path::PathBuf;
use tokio::fs::rename;

pub struct Executor {
    configuration: Configuration,
    token_file: PathBuf,
}

impl Executor {
    fn get_token_file(&self, registry_name: &str) -> Result<PathBuf> {
        let mut token_file = self.token_file.clone();
        token_file.set_file_name(format!(
            "{}-{}",
            token_file
                .file_name()
                .ok_or_else(|| {
                    anyhow!("Failed to get token file name from path: {:?}", token_file)
                })?
                .to_str()
                .ok_or_else(|| {
                    anyhow!(
                        "Failed to convert token file name to string: {:?}",
                        token_file
                    )
                })?,
            registry_name
        ));
        Ok(token_file)
    }

    fn get_token_value(&self, registry_name: &str) -> Option<String> {
        let token_file = self.get_token_file(registry_name).ok()?;
        fs::read_to_string(token_file).ok()
    }

    fn try_create_client(
        &self,
        registry_name: String,
        override_token: Option<String>,
    ) -> Result<Client> {
        let api_url = if let Some(registry) = self.configuration.registries.get(&registry_name) {
            registry.api.clone()
        } else {
            return Err(anyhow::anyhow!("Registry not found in configuration"));
        };
        let token = override_token.or_else(|| self.get_token_value(&registry_name));

        Client::try_new(api_url, token)
    }

    pub fn try_new() -> Result<Self> {
        let configuration = Configuration::get_configuration()?;
        let token_file = Configuration::get_token_file_path()?;
        Ok(Self {
            configuration,
            token_file,
        })
    }

    pub async fn publish(&self, options: PublishOptions) -> Result<()> {
        let progress_actor = SpinnerProgressBar::new("Package published".to_string())?.start();
        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::InProgress(
                "Finding toml".to_string(),
            )))
            .await??;

        let package_path = match options.path {
            Some(path) => match path.trim() {
                "" => current_dir()?,
                path => PathBuf::from(path),
            },
            None => current_dir()?,
        };
        let toml_path = find_toml(&package_path)?;
        let package_root_path = toml_path
            .parent()
            .ok_or(anyhow!("Failed to get package root path"))?;

        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::InProgress(
                "Creating package".to_string(),
            )))
            .await??;

        let mut project = create_project_from_toml_path(&toml_path)?;
        project.validate()?;
        project.validate_files(package_root_path)?;

        let package = Package::from_file(&toml_path, options.compression).map_err(|e| {
            anyhow::anyhow!(
                "Failed to create package based on TOML file: {}",
                e.to_string()
            )
        })?;

        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::InProgress(
                "Creating client".to_string(),
            )))
            .await??;
        let client = self.try_create_client(options.registry_name, options.token)?;

        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::InProgress(
                "Validating version".to_string(),
            )))
            .await??;
        client
            .validate_version(
                package.metadata.clone().name,
                package.metadata.clone().version,
            )
            .await?;

        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::InProgress(
                "Uploading".to_string(),
            )))
            .await??;

        client
            .upload_package(package.to_stream().await?, options.timeout)
            .await?;
        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::Done))
            .await??;
        Ok(())
    }

    pub async fn fetch(&self, options: FetchOptions) -> Result<()> {
        let progress_actor = SpinnerProgressBar::new("Package fetched".to_string())?.start();
        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::InProgress(
                "Updating the repositories".to_string(),
            )))
            .await??;
        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::InProgress(
                "Registering the repository".to_string(),
            )))
            .await??;
        let client = self.try_create_client(options.registry_name.clone(), None)?;

        let version = client
            .get_latest_matching_package(&options.package_name, &options.version_requirement)
            .await?
            .version;

        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::InProgress(
                "Downloading the package".to_string(),
            )))
            .await??;
        let (temporary_package_path, temporary_parent_directory, temporary_package_directory) =
            create_temporary_package_download_path(&options.package_name, &version)?;
        client
            .download_package(&options.package_name, &version, &temporary_package_path)
            .await?;
        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::InProgress(
                "Decompressing the package".to_string(),
            )))
            .await??;
        let unpacked_file_path =
            unpack_package_file(&temporary_package_path, &options.unpack_level)?;
        let target_path = get_download_target_name(
            &options.unpack_level,
            &options.save_path,
            &options.package_name,
            &version,
        );

        rename(unpacked_file_path, target_path).await?;
        temporary_package_directory.close()?;
        temporary_parent_directory.close()?;
        progress_actor
            .send(AdvanceProgressBar(ProgressStatus::Done))
            .await??;

        Ok(())
    }

    pub async fn checksum(&self, options: ChecksumOptions) -> Result<()> {
        let client = self.try_create_client(options.registry_name.clone(), None)?;
        let version = client
            .get_latest_matching_package(&options.package_name, &options.version_requirement)
            .await?
            .version;
        let checksum = client
            .get_package_version(options.package_name.to_string(), version)
            .await?
            .checksum;
        println!("{checksum}");
        Ok(())
    }

    pub async fn inspect(&self, options: InspectOptions) -> Result<()> {
        let package_path = match options.package_path {
            Some(path) => match path.trim() {
                "" => current_dir()?,
                path => PathBuf::from(path),
            },
            None => current_dir()?,
        };

        let toml_path = find_toml(&package_path)?;
        let package_root_path = toml_path
            .parent()
            .ok_or(anyhow!("Failed to get package root path"))?;

        let mut project = create_project_from_toml_path(&toml_path)?;

        project.validate()?;
        project.validate_files(package_root_path)?;
        project.print_inspect_message(options.pretty)?;
        Ok(())
    }

    pub async fn normalize_version(&self, options: NormalizeVersionOptions) -> Result<()> {
        let client = self.try_create_client(options.registry_name.clone(), None)?;
        let version = client
            .get_latest_matching_package(&options.package_name, &options.version_requirement)
            .await?
            .version;
        println!("{}", version);
        Ok(())
    }

    pub async fn login(&self, options: LoginOptions) -> Result<()> {
        let token_value = match options.token {
            Some(token) => token,
            None => Input::<String>::new()
                .report(false)
                .with_prompt("Token")
                .interact_text()?,
        };
        let token_path = self.get_token_file(&options.registry_name)?;

        fs::write(token_path, token_value)?;
        Ok(())
    }

    pub async fn yank(&self, options: YankOptions) -> Result<()> {
        let client = self.try_create_client(options.registry_name.clone(), options.token)?;
        let set_yank = match &options.undo {
            true => "false",
            false => "true",
        };
        let version_rest = client
            .yank_version(
                &options.package_name,
                &options.version_requirement,
                set_yank,
            )
            .await?;
        match version_rest.is_yanked {
            true => println!(
                "{} version {} yank successful",
                &options.package_name, version_rest.version
            ),
            false => println!(
                "{} version {} yank successful undo",
                &options.package_name, version_rest.version
            ),
        }
        Ok(())
    }

    pub async fn add_owner(
        &self,
        owner_options: OwnerOptions,
        user_email: String,
        package_name: String,
    ) -> Result<()> {
        let client = self.try_create_client(owner_options.registry_name, None)?;
        client.add_owner(&package_name, &user_email).await?;

        Ok(())
    }

    pub async fn remove_owner(
        &self,
        owner_options: OwnerOptions,
        user_email: String,
        package_name: String,
    ) -> Result<()> {
        let client = self.try_create_client(owner_options.registry_name, None)?;
        client.delete_owner(&package_name, &user_email).await?;

        Ok(())
    }

    pub async fn list_owners(
        &self,
        owner_options: OwnerOptions,
        package_name: String,
    ) -> Result<()> {
        let client = self.try_create_client(owner_options.registry_name, None)?;
        let owners = client.list_owners(&package_name).await?;

        println!("{}", owners.join("\n"));
        Ok(())
    }

    pub async fn create(&self, options: CreateOptions) -> Result<()> {
        let package_path = options.package_path;
        let mut package_name: String = Input::new()
            .with_prompt("Name of the package")
            .default("deputy_package".to_string())
            .interact_text()?;

        let mut package_dir = if package_path.is_empty() {
            package_name.clone()
        } else {
            format!("{}/{}", package_path, package_name)
        };

        while fs::metadata(&package_dir).is_ok() {
            println!("A folder with the name '{}' already exists.", package_name);
            package_name = Input::new()
                .with_prompt("Please enter a different package name")
                .interact_text()?;
            package_dir = if package_path.is_empty() {
                package_name.clone()
            } else {
                format!("{}/{}", package_path, package_name)
            };
        }

        let src_dir = PathBuf::from(&package_dir).join("src");
        let description: String = Input::new()
            .with_prompt("Describe your package")
            .default("".to_string())
            .interact_text()?;
        let author_name: String = Input::new()
            .with_prompt("Author name")
            .default("John Doe".to_string())
            .interact_text()?;
        let author_email: String = Input::new()
            .with_prompt("Author email")
            .default("your-email@example.com".to_string())
            .interact_text()?;
        let licenses = vec!["Custom SPDX Identifier", "MIT", "Apache-2.0"];
        let license_selection = Select::new()
            .with_prompt("Choose a license")
            .default(1)
            .items(&licenses)
            .interact()?;
        let chosen_license = if licenses[license_selection] == "Custom SPDX Identifier" {
            let mut user_input_license: String = Input::new()
                .with_prompt("Type your license identifier (SPDX ID)")
                .interact_text()?;
            while validate_license(user_input_license.clone()).is_err() {
                println!("Invalid license identifier. Please try again.");
                user_input_license = Input::new()
                    .with_prompt("Type your license identifier (SPDX ID)")
                    .interact_text()?;
            }
            user_input_license
        } else {
            String::from(licenses[license_selection])
        };

        let content_type_strings = ContentType::all_variants();
        let content_type_selection = Select::new()
            .with_prompt("Select package content type")
            .default(0)
            .items(&content_type_strings)
            .interact()
            .unwrap();
        let chosen_content_type = content_type_strings[content_type_selection];
        let type_content = match chosen_content_type {
            "vm" => virtual_machine_fields(),
            "exercise" => exercise_fields(),
            "condition" => condition_fields(),
            "event" => event_fields(),
            "feature" => feature_fields(),
            "malware" => malware_fields(),
            "inject" => inject_fields(),
            "banner" => banner_fields(),
            "other" => other_fields(),
            _ => Err(anyhow::anyhow!("Invalid content type"))?,
        };
        let assets_field: String = ASSETS_REQUIRED_PACKAGE_TYPES
            .contains(&chosen_content_type.try_into()?)
            .then(set_assets_field)
            .unwrap_or_default();

        let content = format!(
            r#"[package]
name = "{package_name}"
description = "{description}"
version = "{version}"
authors = ["{author_name} {author_email}"]
license = "{chosen_license}"
readme  = "README.md"
categories = []
{assets_field}
[content]
type = "{chosen_content_type}"
{type_content}
"#,
            version = options.version,
        );

        fs::create_dir_all(src_dir)?;
        fs::write(format!("{}/package.toml", package_dir), content)?;
        create_default_readme(&package_dir)?;
        println!("Initialized deputy package in {}", package_dir);

        Ok(())
    }

    pub async fn list_packages(&self, list_options: ListOptions) -> Result<()> {
        let client = self.try_create_client(list_options.registry_name.clone(), None)?;
        let mut packages = client.list_packages(&list_options).await?;
        PackageWithVersionsRest::remove_yanked_versions(&mut packages);

        if packages.is_empty() {
            println!("{error} No packages found", error = "Error:".red());
        }
        packages.sort_by(|a, b| a.name.cmp(&b.name));

        if list_options.all_versions {
            for package in &packages {
                print_package_list_entry(package)?;
            }
        } else {
            for package in &packages {
                print_latest_version_package_list_entry(package)?;
            }
        }

        Ok(())
    }

    pub async fn package_info(&self, info_options: InfoOptions) -> Result<()> {
        let client = self.try_create_client(info_options.registry_name.clone(), None)?;
        let mut search_results = client.package_info(&info_options).await?;
        PackageWithVersionsRest::remove_yanked_versions(&mut search_results);

        if search_results.is_empty() {
            println!("{error} Package not found", error = "Error:".red());
            return Ok(());
        }

        let single_match = if search_results.len() == 1 {
            search_results.pop()
        } else {
            search_results
                .iter()
                .find(|package| package.name == info_options.search_term)
                .cloned()
        };

        match single_match {
            Some(mut package) => {
                package.versions.sort_by(|a, b| b.version.cmp(&a.version));

                match info_options.all_versions {
                    true => {
                        for package_version in package.versions.iter() {
                            print_package_info(&package, package_version);
                        }
                    }
                    false => {
                        let package_version =
                            VersionRest::get_latest_package(package.versions.clone())?
                                .ok_or_else(|| anyhow!("Failed to get latest package version"))?;

                        print_package_info(&package, &package_version);

                        let package_count = package.versions.len();
                        if package_count > 1 {
                            println!("{note} There are {package_count} other versions available. Please use the '-a' flag to see them.",  note = "Note:".yellow());
                        }
                    }
                }
            }
            None => {
                let package_names = search_results
                    .into_iter()
                    .map(|package| package.name)
                    .collect::<Vec<String>>()
                    .join(", ");

                println!(
                    "{note} multiple packages found. Please specify a single package.",
                    note = "Note:".yellow()
                );
                println!("{package_names}");
            }
        }
        Ok(())
    }
}
