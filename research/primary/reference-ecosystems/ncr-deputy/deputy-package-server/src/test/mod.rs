pub mod database;
pub mod middleware;

use self::database::MockDatabase;
use crate::{
    routes::{
        basic::{status, version},
        owner::{add_owner, delete_owner, get_all_owners},
        package::{
            add_package, download_file, download_package, get_all_packages, get_all_versions,
            get_package_version, yank_version,
        },
    },
    test::middleware::MockTokenMiddlewareFactory,
    AppState,
};
use actix::Actor;
use actix_web::{
    web::{delete, get, post, put, scope, Data},
    App, HttpServer,
};
use anyhow::{anyhow, Error, Result};
use deputy_library::{constants::default_max_archive_size, test::generate_random_string};
use futures::TryFutureExt;
use get_port::{tcp::TcpPort, Ops, Range};
use rand::Rng;
use std::{
    env,
    fs::{create_dir_all, remove_dir_all},
    path::{Path, PathBuf},
    thread,
    time::Duration,
};
use tokio::{
    sync::oneshot::{channel, Receiver, Sender},
    time::timeout,
    try_join,
};

pub struct TestPackageServerBuilder {
    host: String,
    package_folder: String,
}

impl TestPackageServerBuilder {
    pub fn try_new() -> Result<Self> {
        let temporary_directory = env::temp_dir();
        let randomizer = generate_random_string(10)?;
        let package_folder: PathBuf =
            temporary_directory.join(format!("test-package-folder-{randomizer}"));
        create_dir_all(&package_folder)?;
        let package_folder = package_folder.to_str().unwrap().to_string();
        let address = "127.0.0.1";
        let sleep_duration = Duration::from_millis(rand::random::<u64>() % 5000);

        let mut port = None;
        for _ in 0..5 {
            let random_port_number = rand::thread_rng().gen_range(1024..65535);
            port = TcpPort::in_range(
                address,
                Range {
                    min: random_port_number,
                    max: random_port_number,
                },
            );
            if port.is_some() {
                break;
            }
            thread::sleep(sleep_duration);
        }
        let port = port.ok_or_else(|| anyhow!("Failed to find a free port for the test server"))?;
        let host = format!("{}:{}", address, port);

        Ok(Self {
            host,
            package_folder,
        })
    }

    pub fn host(mut self, host: &str) -> Self {
        self.host = host.to_string();
        self
    }

    pub fn get_host(&self) -> &str {
        &self.host
    }

    pub fn package_folder(mut self, package_folder: &str) -> Self {
        self.package_folder = package_folder.to_string();
        self
    }

    pub fn get_package_folder(&self) -> &str {
        &self.package_folder
    }

    pub fn build(&self) -> TestPackageServer {
        TestPackageServer {
            host: self.host.clone(),
            package_folder: self.package_folder.clone(),
            tx: None,
        }
    }
}

pub struct TestPackageServer {
    host: String,
    package_folder: String,
    tx: Option<Sender<()>>,
}

impl TestPackageServer {
    fn initialize(
        host: String,
        package_folder: String,
        tx: Sender<()>,
        rx: Receiver<()>,
    ) -> Result<()> {
        let runtime = actix_rt::System::new();
        runtime.block_on(async {
            let database = MockDatabase::default().start();
            let app_data: AppState<MockDatabase> = AppState {
                package_folder,
                database_address: database,
                max_archive_size: default_max_archive_size(),
            };
            try_join!(
                HttpServer::new(move || {
                    let app_data = Data::new(app_data.clone());
                    App::new()
                        .app_data(app_data)
                        .service(status)
                        .service(version)
                        .service(
                            scope("/api").service(
                                scope("/v1").service(
                                    scope("/package")
                                        .route("", get().to(get_all_packages::<MockDatabase>))
                                        .service(
                                            scope("/{package_name}")
                                                .route(
                                                    "",
                                                    get().to(get_all_versions::<MockDatabase>),
                                                )
                                                .service(
                                                    scope("/owner")
                                                        .route(
                                                            "",
                                                            get()
                                                                .to(get_all_owners::<MockDatabase>),
                                                        )
                                                        .service(
                                                            scope("")
                                                                .route(
                                                                    "",
                                                                    post().to(add_owner::<
                                                                        MockDatabase,
                                                                    >),
                                                                )
                                                                .route(
                                                                    "/{owner_email}",
                                                                    delete().to(delete_owner::<
                                                                        MockDatabase,
                                                                    >),
                                                                )
                                                                .wrap(MockTokenMiddlewareFactory),
                                                        ),
                                                )
                                                .service(
                                                    scope("/{version}")
                                                        .route(
                                                            "/download",
                                                            get().to(download_package::<
                                                                MockDatabase,
                                                            >),
                                                        )
                                                        .route(
                                                            "/path/{tail:.*}",
                                                            get().to(download_file::<MockDatabase>),
                                                        )
                                                        .route(
                                                            "",
                                                            get().to(get_package_version::<
                                                                MockDatabase,
                                                            >),
                                                        )
                                                        .service(
                                                            scope("")
                                                                .route(
                                                                    "/yank/{set_yank}",
                                                                    put().to(yank_version::<
                                                                        MockDatabase,
                                                                    >),
                                                                )
                                                                .wrap(MockTokenMiddlewareFactory),
                                                        ),
                                                ),
                                        )
                                        .service(
                                            scope("")
                                                .service(scope("").route(
                                                    "",
                                                    post().to(add_package::<MockDatabase>),
                                                ))
                                                .wrap(MockTokenMiddlewareFactory),
                                        ),
                                ),
                            ),
                        )
                })
                .bind(host)
                .unwrap()
                .run()
                .map_err(|error| anyhow!("Failed to start the server: {:?}", error)),
                async move {
                    tx.send(())
                        .map_err(|error| anyhow!("Failed to send message: {:?}", error))?;
                    rx.await.unwrap();
                    Ok::<(), Error>(())
                },
            )
            .unwrap();
        });
        Ok(())
    }

    pub async fn start(mut self) -> Result<()> {
        let host = self.host.clone();
        let package_folder = self.package_folder.clone();

        let (tx, rx) = channel::<()>();
        let (tx1, rx1) = channel::<()>();
        thread::spawn(|| {
            Self::initialize(host, package_folder, tx, rx1).unwrap();
        });
        timeout(Duration::from_secs(3), rx).await??;

        self.tx = Some(tx1);
        Ok(())
    }
}

impl Drop for TestPackageServer {
    fn drop(&mut self) {
        if Path::new(&self.package_folder).is_dir() {
            remove_dir_all(&self.package_folder).unwrap();
        }
        if let Some(tx) = self.tx.take() {
            tx.send(()).unwrap();
        }
    }
}
