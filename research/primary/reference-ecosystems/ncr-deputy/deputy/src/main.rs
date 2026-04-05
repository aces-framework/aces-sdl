use anyhow::Result;
use clap::{Parser, Subcommand};
use deputy::{
    commands::{
        ChecksumOptions, CreateOptions, FetchOptions, InfoOptions, InspectOptions, ListOptions,
        LoginOptions, NormalizeVersionOptions, OwnerOptions, OwnerSubcommands, PublishOptions,
        YankOptions,
    },
    executor::Executor,
    helpers::print_error_message,
};

#[derive(Parser)]
#[clap(author, version, about, long_about = None)]
#[clap(name = "deputy")]
struct Cli {
    #[clap(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    #[clap(about = "Upload package")]
    Publish(PublishOptions),
    #[clap(about = "Download package")]
    Fetch(FetchOptions),
    #[clap(about = "Download package checksum")]
    Checksum(ChecksumOptions),
    #[clap(about = "Validate local package.toml file")]
    Inspect(InspectOptions),
    #[clap(about = "Return latest version of package")]
    NormalizeVersion(NormalizeVersionOptions),
    #[clap(about = "Log in to registry")]
    Login(LoginOptions),
    #[clap(about = "Remove previously published version of package from registry")]
    Yank(YankOptions),
    #[clap(about = "Manage the owners of package on the registry")]
    Owner(OwnerOptions),
    #[clap(about = "Create new package")]
    Create(CreateOptions),
    #[clap(about = "List all packages")]
    List(ListOptions),
    #[clap(about = "Get detailed information of package")]
    Info(InfoOptions),
}

#[actix_rt::main]
async fn main() -> Result<()> {
    let args = Cli::parse();
    let executor = Executor::try_new()?;

    let result = match args.command {
        Commands::Publish(options) => executor.publish(options).await,
        Commands::Fetch(options) => executor.fetch(options).await,
        Commands::Checksum(options) => executor.checksum(options).await,
        Commands::Inspect(options) => executor.inspect(options).await,
        Commands::NormalizeVersion(options) => executor.normalize_version(options).await,
        Commands::Login(options) => executor.login(options).await,
        Commands::Yank(options) => executor.yank(options).await,
        Commands::Owner(options) => match options.subcommands.clone() {
            OwnerSubcommands::Add {
                user_email,
                package_name,
            } => executor.add_owner(options, user_email, package_name).await,
            OwnerSubcommands::Remove {
                user_email,
                package_name,
            } => {
                executor
                    .remove_owner(options, user_email, package_name)
                    .await
            }
            OwnerSubcommands::List { package_name } => {
                executor.list_owners(options, package_name).await
            }
        },
        Commands::Create(options) => executor.create(options).await,
        Commands::List(options) => executor.list_packages(options).await,
        Commands::Info(options) => executor.package_info(options).await,
    };
    if let Err(error) = result {
        print_error_message(error);
        std::process::exit(1);
    }

    Ok(())
}
