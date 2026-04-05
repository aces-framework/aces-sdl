#![allow(dead_code)]

use actix::Actor;
use actix_http::Payload;
use actix_http::{HttpMessage, Request};
use actix_web::web::{Bytes, Data};
use actix_web::{test, web::post, App};
use anyhow::Result;
use deputy_library::constants::default_max_archive_size;
use deputy_library::{
    package::{Package, PackageStream},
    test::TempArchive,
};
use deputy_package_server::{middleware::authentication::local_token::UserToken, AppState};
use deputy_package_server::{routes::package::add_package, test::database::MockDatabase};
use std::rc::Rc;
use tempfile::TempDir;

pub trait BodyTest {
    fn as_str(&self) -> &str;
}

impl BodyTest for Bytes {
    fn as_str(&self) -> &str {
        std::str::from_utf8(self).unwrap()
    }
}

pub fn setup_package_server(
    max_archive_size: Option<u64>,
) -> Result<(TempDir, Data<AppState<MockDatabase>>)> {
    let package_folder = TempDir::new()?;
    let package_folder_string = package_folder.path().to_str().unwrap().to_string();

    let database_address = MockDatabase::default().start();
    Ok((
        package_folder,
        Data::new(AppState {
            package_folder: package_folder_string,
            database_address,
            max_archive_size: max_archive_size.unwrap_or(default_max_archive_size()),
        }),
    ))
}

pub fn set_mock_user_token(request: &Request) {
    request
        .extensions_mut()
        .insert::<Rc<UserToken>>(Rc::new(UserToken {
            id: "test-id".to_string(),
            email: "test-email".to_string(),
        }));
}

pub async fn upload_test_package(app_state: &Data<AppState<MockDatabase>>) -> Result<String> {
    let app = test::init_service(
        App::new()
            .app_data(app_state.clone())
            .route("/package", post().to(add_package::<MockDatabase>)),
    )
    .await;

    let archive = TempArchive::builder().build()?;
    let test_package: Package = (&archive).try_into()?;
    let package_name = test_package.metadata.name.clone();

    let stream: PackageStream = test_package.to_stream().await?;
    let request = test::TestRequest::post().uri("/package").to_request();
    let (request, _) = request.replace_payload(Payload::from(stream));
    set_mock_user_token(&request);
    test::call_service(&app, request).await;

    Ok(package_name)
}
