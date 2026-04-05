use crate::constants::{
    fetching::{DEFAULT_PACKAGE_VERSION_REQUIREMENT, DEFAULT_SAVE_PATH},
    inspecting::DEFAULT_PACKAGE_PATH,
    publishing::VALID_COMPRESSION_RATES,
    DEFAULT_REGISTRY_NAME,
};
use clap::{Args, Subcommand, ValueEnum};

#[derive(ValueEnum, Clone, Debug)]
pub enum UnpackLevel {
    Raw,
    Uncompressed,
    Regular,
}

#[derive(Debug, Args)]
pub struct FetchOptions {
    pub package_name: String,
    #[clap(value_enum, short, long, default_value_t = UnpackLevel::Regular)]
    pub unpack_level: UnpackLevel,
    #[clap(short, long, default_value = DEFAULT_PACKAGE_VERSION_REQUIREMENT, help = "Version of the package to fetch")]
    pub version_requirement: String,
    #[clap(short, long, default_value = DEFAULT_SAVE_PATH, help = "Save path for the package")]
    pub save_path: String,
    #[clap(
        short,
        long,
        default_value = DEFAULT_REGISTRY_NAME,
        help = "Registry to use for package fetching"
    )]
    pub registry_name: String,
}

#[derive(Debug, Args)]
pub struct ChecksumOptions {
    pub package_name: String,
    #[clap(short, long, default_value = DEFAULT_PACKAGE_VERSION_REQUIREMENT, help = "Version of the package to fetch")]
    pub version_requirement: String,
    #[clap(
        short,
        long,
        default_value = DEFAULT_REGISTRY_NAME,
        help = "Registry to use for package fetching"
    )]
    pub registry_name: String,
}

#[derive(Debug, Args)]
pub struct PublishOptions {
    #[clap(
        short,
        long,
        default_value_t = 1_000_000,
        help = "Timeout before publish fails"
    )]
    pub(crate) timeout: u64,
    #[clap(
        short,
        long,
        value_parser = clap::value_parser!(u32).range(VALID_COMPRESSION_RATES),
        default_value_t = 0,
        help = format!("Compression rate before upload. Valid values {:?}",VALID_COMPRESSION_RATES)
    )]
    pub(crate) compression: u32,
    #[clap(
        short,
        long,
        default_value = DEFAULT_REGISTRY_NAME,
        help = "Registry to use for publishing"
    )]
    pub registry_name: String,
    #[clap(short = 'T', long, help = "Override the login token")]
    pub token: Option<String>,
    #[clap(short, long, help = "Path to the package to publish")]
    pub path: Option<String>,
}

#[derive(Debug, Args)]
pub struct InspectOptions {
    #[clap(short, long, help = "Path to the package")]
    pub package_path: Option<String>,
    #[clap(long, help = "Pretty print output")]
    pub pretty: bool,
}

#[derive(Debug, Args)]
pub struct NormalizeVersionOptions {
    pub package_name: String,
    #[clap(short, long, default_value = DEFAULT_PACKAGE_VERSION_REQUIREMENT, help = "Version of the package to fetch")]
    pub version_requirement: String,
    #[clap(
        short,
        long,
        default_value = DEFAULT_REGISTRY_NAME,
        help = "Registry to use for versioning"
    )]
    pub registry_name: String,
}

#[derive(Debug, Args)]
pub struct LoginOptions {
    #[clap(
        short,
        long,
        default_value = DEFAULT_REGISTRY_NAME,
        help = "Registry to use for publishing"
    )]
    pub registry_name: String,
    #[clap(short = 'T', long, help = "Set the login token as parameter")]
    pub token: Option<String>,
}

#[derive(Debug, Args)]
pub struct YankOptions {
    pub package_name: String,
    #[clap(help = "Version of the package to yank")]
    pub version_requirement: String,
    #[clap(
    short,
    long,
    default_value = DEFAULT_REGISTRY_NAME,
    help = "Registry to use for version yanking"
    )]
    pub registry_name: String,
    #[clap(short, long, help = "Undo yank")]
    pub undo: bool,
    #[clap(short = 'T', long, help = "Override the login token")]
    pub token: Option<String>,
}

#[derive(Subcommand, Debug, Clone)]
pub enum OwnerSubcommands {
    Add {
        user_email: String,
        package_name: String,
    },
    Remove {
        user_email: String,
        package_name: String,
    },
    List {
        package_name: String,
    },
}

#[derive(Debug, Args, Clone)]
pub struct OwnerOptions {
    #[clap(
        short,
        long,
        default_value = DEFAULT_REGISTRY_NAME,
        help = "Registry to use for versioning"
    )]
    pub registry_name: String,
    #[clap(subcommand)]
    pub subcommands: OwnerSubcommands,
}

#[derive(Debug, Args)]
pub struct CreateOptions {
    #[clap(
        short = 'p',
        long,
        default_value = DEFAULT_PACKAGE_PATH,
        help = "Path for the package"
    )]
    pub package_path: String,
    #[clap(
        short,
        long,
        default_value = "0.1.0",
        help = "Initial version for the package.toml"
    )]
    pub version: String,
}

#[derive(Debug, Args)]
pub struct ListOptions {
    #[clap(
        short,
        long,
        default_value = DEFAULT_REGISTRY_NAME,
        help = "Registry to use for versioning"
    )]
    pub registry_name: String,
    #[clap(
        help = "List packages matching the search term. If no search term is provided, all packages are listed."
    )]
    pub search_term: Option<String>,
    #[clap(short = 't', long = "type", help = "Filter packages by type")]
    pub package_type: Option<String>,
    #[clap(
        short = 'c',
        long = "category",
        help = "Filter packages by category. Supports multiple categories separated by commas. "
    )]
    pub category: Option<String>,
    #[clap(short = 'a', long, help = "List all versions of the package")]
    pub all_versions: bool,
}

#[derive(Debug, Args)]
pub struct InfoOptions {
    #[clap(
        short,
        long,
        default_value = DEFAULT_REGISTRY_NAME,
        help = "Registry to use for versioning"
    )]
    pub registry_name: String,
    #[clap(help = "Show package details.")]
    pub search_term: String,
    #[clap(
        short = 'a',
        help = "Show all versions of the package. By default, only the latest version is shown."
    )]
    pub all_versions: bool,
}
