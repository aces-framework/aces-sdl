mod common;

#[cfg(test)]
mod tests {

    use crate::common::{set_mock_user_token, setup_package_server, upload_test_package, BodyTest};
    use actix_http::Payload;
    use actix_web::dev::ServiceResponse;
    use actix_web::http::header::ContentType;
    use actix_web::{
        body::to_bytes,
        test,
        web::{get, post, put, scope, Bytes},
        App,
    };
    use anyhow::Result;
    use deputy_library::{
        package::{Package, PackageMetadata, PackageStream},
        test::TempArchive,
    };
    use deputy_package_server::{
        routes::package::{
            add_package, download_file, download_package, get_all_categories, yank_version,
        },
        test::{database::MockDatabase, middleware::MockTokenMiddlewareFactory},
    };
    use futures::StreamExt;
    use std::io::{Read, Write};
    use std::path::PathBuf;

    #[actix_web::test]
    async fn successfully_add_package() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let app = test::init_service(
            App::new()
                .app_data(app_state)
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

        let response = test::call_service(&app, request).await;
        assert!(response.status().is_success());
        assert!(PathBuf::from(package_folder.path())
            .join(package_name)
            .exists());
        package_folder.close()?;
        Ok(())
    }

    #[actix_web::test]
    async fn send_invalid_package_checksum() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let app = test::init_service(
            App::new()
                .app_data(app_state)
                .route("/package", post().to(add_package::<MockDatabase>)),
        )
        .await;

        let archive = TempArchive::builder().build()?;
        let mut test_package: Package = (&archive).try_into()?;

        test_package.metadata.checksum = "invalid".to_string();
        let stream: PackageStream = test_package.to_stream().await?;
        let request = test::TestRequest::post().uri("/package").to_request();
        let (request, _) = request.replace_payload(Payload::from(stream));
        set_mock_user_token(&request);

        let response = test::call_service(&app, request).await;

        assert!(response.status().is_client_error());
        let body = to_bytes(response.into_body()).await.unwrap();
        assert_eq!(body.as_str(), "Failed to validate the package metadata");

        package_folder.close()?;
        Ok(())
    }

    #[actix_web::test]
    async fn send_invalid_package_name() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let app = test::init_service(
            App::new()
                .app_data(app_state)
                .route("/package", post().to(add_package::<MockDatabase>)),
        )
        .await;

        let long_name = "package".repeat(1000);
        let invalid_names = vec![
            &long_name,
            "'; DROP TABLE packages; --",
            "'; SELECT * FROM users WHERE '1'='1",
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "../../../../etc/passwd",
            "../package",
            "包裹",
            "パッケージ",
            "пакет",
            " leading",
            "trailing ",
            "multiple  spaces",
            "-leading",
            "trailing-",
            "_leading",
            "trailing_",
            "-----",
            "_____",
            "-_-",
            "_-_",
            "name\nwith\nnewlines",
            "name\twith\ttabs",
            "name\rwith\rreturns",
            "name\u{0}with\u{0}nulls",
            "name\u{7F}with\u{7F}del",
            "name\u{80}with\u{80}control",
            "name\u{FFFD}with\u{FFFD}replacement",
            "name\u{1F600}with\u{1F600}emoji",
        ];
        let invalid_special_characters = "!@#$%^&*()+{}|:\"<>?`=[]\\;',./";
        let mut all_invalid_names: Vec<String> =
            invalid_names.iter().map(ToString::to_string).collect();

        all_invalid_names.extend(
            invalid_special_characters
                .chars()
                .map(|char| format!("package{char}name")),
        );

        let archive = TempArchive::builder().build()?;

        for name in all_invalid_names {
            let mut test_package: Package = (&archive).try_into()?;
            test_package.metadata.name = name.to_string();
            let stream: PackageStream = test_package.to_stream().await?;
            let request = test::TestRequest::post().uri("/package").to_request();
            let (request, _) = request.replace_payload(Payload::from(stream));
            set_mock_user_token(&request);

            let response = test::call_service(&app, request).await;

            assert!(response.status().is_client_error());
            let body = to_bytes(response.into_body()).await.unwrap();
            assert_eq!(body.as_str(), "Failed to validate the package metadata");
        }
        package_folder.close()?;

        Ok(())
    }

    #[actix_web::test]
    async fn submit_package_with_same_version_twice() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let app = test::init_service(
            App::new()
                .app_data(app_state)
                .route("/package", post().to(add_package::<MockDatabase>)),
        )
        .await;

        let archive = TempArchive::builder().build()?;
        let test_package: Package = (&archive).try_into()?;

        let stream: PackageStream = test_package.to_stream().await?;
        let request = test::TestRequest::post().uri("/package").to_request();
        let (request, _) = request.replace_payload(Payload::from(stream));
        set_mock_user_token(&request);

        test::call_service(&app, request).await;

        let second_archive = TempArchive::builder().build()?;
        let second_test_package: Package = (&second_archive).try_into()?;
        let second_stream: PackageStream = second_test_package.to_stream().await?;
        let second_request = test::TestRequest::post().uri("/package").to_request();
        let (second_request, _) = second_request.replace_payload(Payload::from(second_stream));
        set_mock_user_token(&second_request);

        let second_response = test::call_service(&app, second_request).await;

        assert!(second_response.status().is_client_error());
        let body = to_bytes(second_response.into_body()).await.unwrap();
        assert_eq!(
            body.as_str(),
            "Package version on the server is either same or later: 1.0.4"
        );

        package_folder.close()?;
        Ok(())
    }

    #[actix_web::test]
    async fn download_package_with_name_and_version() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let archive = TempArchive::builder().build()?;
        let test_package: Package = (&archive).try_into()?;

        let package_name = test_package.metadata.name.clone();
        let package_version = test_package.metadata.version.clone();

        let app = test::init_service(
            App::new().app_data(app_state).service(
                scope("/package")
                    .service(
                        scope("/{package_name}").service(
                            scope("/{version}")
                                .route("/download", get().to(download_package::<MockDatabase>)),
                        ),
                    )
                    .route("", post().to(add_package::<MockDatabase>)),
            ),
        )
        .await;
        let stream: PackageStream = test_package.to_stream().await?;
        let request = test::TestRequest::post().uri("/package").to_request();
        let (request, _) = request.replace_payload(Payload::from(stream));
        set_mock_user_token(&request);

        test::call_service(&app, request).await;

        let request = test::TestRequest::get()
            .uri(&format!(
                "/package/{}/{}/download",
                package_name, package_version
            ))
            .to_request();

        let body = test::call_and_read_body(&app, request).await;
        let search_string = b"and we spent 300 manhours on it...";
        assert!(body
            .windows(search_string.len())
            .any(|window| window == search_string));

        package_folder.close()?;
        Ok(())
    }

    #[actix_web::test]
    async fn download_file_from_package() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let archive = TempArchive::builder().zero_filetimes(false).build()?;
        let test_package: Package = (&archive).try_into()?;

        let package_name = test_package.metadata.name.clone();
        let package_version = test_package.metadata.version.clone();

        let app = test::init_service(
            App::new().app_data(app_state).service(
                scope("/package")
                    .service(
                        scope("/{package_name}").service(
                            scope("/{version}")
                                .route("/path/{tail:.*}", get().to(download_file::<MockDatabase>)),
                        ),
                    )
                    .route("", post().to(add_package::<MockDatabase>)),
            ),
        )
        .await;
        let stream: PackageStream = test_package.to_stream().await?;
        let request = test::TestRequest::post().uri("/package").to_request();
        let (request, _) = request.replace_payload(Payload::from(stream));
        set_mock_user_token(&request);

        test::call_service(&app, request).await;

        let request = test::TestRequest::get()
            .uri(&format!(
                "/package/{}/{}/path/src/test_file.txt",
                package_name, package_version
            ))
            .to_request();

        let body = test::call_and_read_body(&app, request).await;
        let search_string = b"Mauris elementum non quam laoreet tristique.";
        assert!(body
            .windows(search_string.len())
            .any(|window| window == search_string));

        package_folder.close()?;
        Ok(())
    }

    #[actix_web::test]
    async fn yank_package() -> Result<()> {
        let (_package_folder, app_state) = setup_package_server(None)?;
        let package_name = upload_test_package(&app_state).await.unwrap();
        let package_version = "1.0.4".to_string();
        let app = test::init_service(
            App::new()
                .app_data(app_state)
                .route(
                    "/package/{package_name}/{version}/yank/{set_yank}",
                    put().to(yank_version::<MockDatabase>),
                )
                .wrap(MockTokenMiddlewareFactory),
        )
        .await;

        let uri = format!("/package/{}/{}/yank/true", package_name, package_version);
        let request = test::TestRequest::put().uri(uri.as_str()).to_request();
        set_mock_user_token(&request);
        let response = test::call_service(&app, request).await;
        assert!(response.status().is_success());
        let body = to_bytes(response.into_body()).await.unwrap();
        let search_string = b"isYanked\":true";
        assert!(body
            .windows(search_string.len())
            .any(|window| window == search_string));

        Ok(())
    }

    #[actix_web::test]
    async fn test_get_all_categories() -> Result<()> {
        let (_package_folder, app_state) = setup_package_server(None)?;
        upload_test_package(&app_state).await.unwrap();

        let app = test::init_service(
            App::new()
                .app_data(app_state)
                .route("/category", get().to(get_all_categories::<MockDatabase>))
                .wrap(MockTokenMiddlewareFactory),
        )
        .await;

        let request = test::TestRequest::get().uri("/category").to_request();
        set_mock_user_token(&request);
        let response = test::call_service(&app, request).await;
        assert!(response.status().is_success());
        let body = to_bytes(response.into_body()).await.unwrap();
        let search_string = b"\"name\":\"category1\"";
        assert!(body
            .windows(search_string.len())
            .any(|window| window == search_string));

        Ok(())
    }

    #[actix_web::test]
    async fn invalid_package_file_type_is_rejected() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let app = test::init_service(
            App::new()
                .app_data(app_state)
                .route("/package", post().to(add_package::<MockDatabase>)),
        )
        .await;

        let archive = TempArchive::builder().build()?;
        let test_package: Package = (&archive).try_into()?;

        let metadata_bytes = Vec::try_from(&test_package.metadata)?;
        let metadata_stream: PackageStream =
            Box::pin(futures::stream::iter(vec![Ok(Bytes::from(metadata_bytes))]));

        let mut not_a_package_file = tempfile::NamedTempFile::new_in(&archive.root_dir)?;
        not_a_package_file.write_all(b"I am not a package")?;
        let archive_size = not_a_package_file.as_file().metadata()?.len();

        let mut file_content = Vec::new();
        not_a_package_file
            .as_file_mut()
            .read_to_end(&mut file_content)?;

        let file_stream = futures::stream::iter(vec![Ok(Bytes::from(file_content))]);

        let stream = metadata_stream
            .chain(futures::stream::once(async move {
                Ok(Bytes::from(archive_size.to_le_bytes().to_vec()))
            }))
            .chain(file_stream);
        let boxed_stream: PackageStream = stream.boxed_local();

        let request = test::TestRequest::post()
            .uri("/package")
            .insert_header(ContentType::plaintext())
            .to_request();

        let (request, _) = request.replace_payload(Payload::from(boxed_stream));
        set_mock_user_token(&request);

        let response = test::call_service(&app, request).await;

        assert!(response.status().is_client_error());
        let body = test::read_body(response).await;
        assert_eq!(body.as_str(), "Package did not pass validation");
        package_folder.close()?;

        Ok(())
    }

    #[actix_web::test]
    async fn oversized_package_is_rejected() -> Result<()> {
        let max_package_size = 1024;
        let (package_folder, app_state) = setup_package_server(Some(max_package_size))?;
        let app = test::init_service(
            App::new()
                .app_data(app_state)
                .route("/package", post().to(add_package::<MockDatabase>)),
        )
        .await;

        let archive = TempArchive::builder().build()?;
        let test_package: Package = (&archive).try_into()?;

        let stream: PackageStream = test_package.to_stream().await?;
        let request = test::TestRequest::post().uri("/package").to_request();
        let (request, _) = request.replace_payload(Payload::from(stream));
        set_mock_user_token(&request);

        let response = test::call_service(&app, request).await;

        assert!(response.status().is_client_error());
        let body = test::read_body(response).await;
        assert_eq!(body.as_str(), "Package did not pass validation");
        package_folder.close()?;

        Ok(())
    }

    #[actix_web::test]
    async fn yanked_package_can_not_be_fetched() -> Result<()> {
        let (_package_folder, app_state) = setup_package_server(None)?;
        let package_name = upload_test_package(&app_state).await.unwrap();
        let package_version = "1.0.4".to_string();
        let app = test::init_service(
            App::new().app_data(app_state).service(
                scope("/package").service(
                    scope("/{package_name}").service(
                        scope("/{version}")
                            .route("/yank/{set_yank}", post().to(yank_version::<MockDatabase>))
                            .route("/download", get().to(download_package::<MockDatabase>)),
                    ),
                ),
            ),
        )
        .await;

        let uri = format!("/package/{package_name}/{package_version}/yank/true");
        let request = test::TestRequest::post().uri(uri.as_str()).to_request();
        set_mock_user_token(&request);
        let response = test::call_service(&app, request).await;

        assert!(response.status().is_success());
        let body = to_bytes(response.into_body()).await.unwrap();
        assert!(body.as_str().contains("\"isYanked\":true"));

        let fetch_request_uri = format!("/package/{package_name}/{package_version}/download");
        let fetch_request = test::TestRequest::get()
            .uri(&fetch_request_uri)
            .to_request();
        let fetch_response = test::call_service(&app, fetch_request).await;

        assert!(fetch_response.status().is_client_error());
        let body = to_bytes(fetch_response.into_body()).await.unwrap();
        assert_eq!(body.as_str(), "Package has been yanked");

        Ok(())
    }

    #[actix_web::test]
    async fn files_from_yanked_package_can_not_be_fetched() -> Result<()> {
        let (_package_folder, app_state) = setup_package_server(None)?;
        let package_name = upload_test_package(&app_state).await.unwrap();
        let package_version = "1.0.4".to_string();
        let app = test::init_service(
            App::new().app_data(app_state).service(
                scope("/package").service(
                    scope("/{package_name}").service(
                        scope("/{version}")
                            .route("/yank/{set_yank}", post().to(yank_version::<MockDatabase>))
                            .route("/path/{tail:.*}", get().to(download_file::<MockDatabase>)),
                    ),
                ),
            ),
        )
        .await;

        let uri = format!("/package/{package_name}/{package_version}/yank/true");
        let request = test::TestRequest::post().uri(uri.as_str()).to_request();
        set_mock_user_token(&request);
        let response = test::call_service(&app, request).await;

        assert!(response.status().is_success());
        let body = to_bytes(response.into_body()).await.unwrap();
        assert!(body.as_str().contains("\"isYanked\":true"));

        let fetch_file_request_uri =
            format!("/package/{package_name}/{package_version}/path/src/test_file.txt");
        let download_request = test::TestRequest::get()
            .uri(&fetch_file_request_uri)
            .to_request();
        let fetch_file_response = test::call_service(&app, download_request).await;

        assert!(fetch_file_response.status().is_client_error());
        let body = to_bytes(fetch_file_response.into_body()).await.unwrap();
        assert_eq!(body.as_str(), "Package has been yanked");

        Ok(())
    }

    async fn post_package_with_modified_metadata<F>(modify_metadata: F) -> Result<ServiceResponse>
    where
        F: FnOnce(&mut PackageMetadata),
    {
        let (package_folder, app_state) = setup_package_server(None)?;
        let app = test::init_service(
            App::new()
                .app_data(app_state)
                .route("/package", post().to(add_package::<MockDatabase>)),
        )
        .await;

        let archive = TempArchive::builder().build()?;
        let mut test_package: Package = (&archive).try_into()?;

        modify_metadata(&mut test_package.metadata);

        let package_stream = test_package.to_stream().await?;
        let request = test::TestRequest::post()
            .uri("/package")
            .insert_header(ContentType::plaintext())
            .to_request();

        let (request, _) = request.replace_payload(Payload::from(package_stream));
        set_mock_user_token(&request);

        let response = test::call_service(&app, request).await;
        package_folder.close()?;

        Ok(response)
    }

    #[actix_web::test]
    async fn mismatched_name_metadata_fails_consistency_check() -> Result<()> {
        let response = post_package_with_modified_metadata(|metadata| {
            metadata.name = "invalid".to_string();
        })
        .await?;

        assert!(response.status().is_client_error());
        let body = test::read_body(response).await;
        assert_eq!(body.as_str(), "Package did not pass validation");

        Ok(())
    }

    #[actix_web::test]
    async fn mismatched_package_type_metadata_fails_consistency_check() -> Result<()> {
        let response = post_package_with_modified_metadata(|metadata| {
            metadata.package_type = deputy_library::project::ContentType::Other;
        })
        .await?;

        assert!(response.status().is_client_error());
        let body = test::read_body(response).await;
        assert_eq!(body.as_str(), "Package did not pass validation");

        Ok(())
    }

    #[actix_web::test]
    async fn mismatched_version_metadata_fails_consistency_check() -> Result<()> {
        let response = post_package_with_modified_metadata(|metadata| {
            metadata.version = "99.99.99".to_string();
        })
        .await?;

        assert!(response.status().is_client_error());
        let body = test::read_body(response).await;
        assert_eq!(body.as_str(), "Package did not pass validation");

        Ok(())
    }

    #[actix_web::test]
    async fn mismatched_description_metadata_fails_consistency_check() -> Result<()> {
        let response = post_package_with_modified_metadata(|metadata| {
            metadata.description = "Don't mind me...".to_string();
        })
        .await?;

        assert!(response.status().is_client_error());
        let body = test::read_body(response).await;
        assert_eq!(body.as_str(), "Package did not pass validation");

        Ok(())
    }

    #[actix_web::test]
    async fn mismatched_license_metadata_fails_consistency_check() -> Result<()> {
        let response = post_package_with_modified_metadata(|metadata| {
            metadata.license = "WTFPL".to_string();
        })
        .await?;

        assert!(response.status().is_client_error());
        let body = test::read_body(response).await;
        assert_eq!(body.as_str(), "Package did not pass validation");

        Ok(())
    }

    #[actix_web::test]
    async fn mismatched_readme_path_metadata_fails_consistency_check() -> Result<()> {
        let response = post_package_with_modified_metadata(|metadata| {
            metadata.readme_path = "../../../../etc/passwd".to_string();
        })
        .await?;

        assert!(response.status().is_client_error());
        let body = test::read_body(response).await;
        assert_eq!(body.as_str(), "Package did not pass validation");

        Ok(())
    }

    #[actix_web::test]
    async fn mismatched_package_size_metadata_fails_consistency_check() -> Result<()> {
        let response = post_package_with_modified_metadata(|metadata| {
            metadata.package_size = 0;
        })
        .await?;

        assert!(response.status().is_client_error());
        let body = test::read_body(response).await;
        assert_eq!(body.as_str(), "Package did not pass validation");

        Ok(())
    }

    #[actix_web::test]
    async fn mismatched_categories_metadata_fails_consistency_check() -> Result<()> {
        let response = post_package_with_modified_metadata(|metadata| {
            metadata.categories = Some(vec!["invalid".to_string()]);
        })
        .await?;

        assert!(response.status().is_client_error());
        let body = test::read_body(response).await;
        assert_eq!(body.as_str(), "Package did not pass validation");

        Ok(())
    }

    #[actix_web::test]
    async fn download_file_from_package_with_percent_encoded_filename() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let archive = TempArchive::builder().zero_filetimes(false).build()?;
        let filename_prefix = "你好abcABCæøåÆØÅäöüïëêîâéíáóúýñ½§!#¤%&()=`@£$€{[]}+´¨^~'-_,;";
        let filename_suffix = ".txt";
        let file_content_bytes = "Lörem ipsüm dõlõr sit ämet".as_bytes();
        let mut special_file = tempfile::Builder::new()
            .prefix(filename_prefix)
            .suffix(filename_suffix)
            .rand_bytes(0)
            .tempfile_in(&archive.src_dir)?;
        special_file.write_all(file_content_bytes)?;

        let test_package: Package = (&archive).try_into()?;

        let package_name = test_package.metadata.name.clone();
        let package_version = test_package.metadata.version.clone();

        let app = test::init_service(
            App::new().app_data(app_state).service(
                scope("/package")
                    .service(
                        scope("/{package_name}").service(
                            scope("/{version}")
                                .route("/path/{tail:.*}", get().to(download_file::<MockDatabase>)),
                        ),
                    )
                    .route("", post().to(add_package::<MockDatabase>)),
            ),
        )
        .await;
        let stream: PackageStream = test_package.to_stream().await?;
        let request = test::TestRequest::post().uri("/package").to_request();
        let (request, _) = request.replace_payload(Payload::from(stream));
        set_mock_user_token(&request);

        test::call_service(&app, request).await;

        let filename = format!("{filename_prefix}{filename_suffix}");
        let encoded_filename = urlencoding::encode(&filename);

        let request = test::TestRequest::get()
            .uri(&format!(
                "/package/{package_name}/{package_version}/path/src/{encoded_filename}",
            ))
            .to_request();

        let body = test::call_and_read_body(&app, request).await;
        assert!(body
            .windows(file_content_bytes.len())
            .any(|window| window == file_content_bytes));

        package_folder.close()?;
        Ok(())
    }

    #[actix_web::test]
    async fn download_file_endpoint_has_correct_attachment_headers_and_filenames() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let archive = TempArchive::builder().zero_filetimes(false).build()?;
        let test_package: Package = (&archive).try_into()?;
        let filename_prefix = "你好abcABCæøåÆØÅäöüïëêîâéíáóúýñ½§!#¤%&()=`@£$€{[]}+´¨^~'-_,;";
        let filename_suffix = ".txt";
        let file_content_bytes = "Lörem ipsüm dõlõr sit ämet".as_bytes();
        let mut special_file = tempfile::Builder::new()
            .prefix(filename_prefix)
            .suffix(filename_suffix)
            .rand_bytes(0)
            .tempfile_in(&archive.src_dir)?;
        special_file.write_all(file_content_bytes)?;

        let package_name = test_package.metadata.name.clone();
        let package_version = test_package.metadata.version.clone();

        let app = test::init_service(
            App::new().app_data(app_state).service(
                scope("/package")
                    .service(
                        scope("/{package_name}").service(
                            scope("/{version}")
                                .route("/path/{tail:.*}", get().to(download_file::<MockDatabase>)),
                        ),
                    )
                    .route("", post().to(add_package::<MockDatabase>)),
            ),
        )
        .await;
        let stream: PackageStream = test_package.to_stream().await?;
        let request = test::TestRequest::post().uri("/package").to_request();
        let (request, _) = request.replace_payload(Payload::from(stream));
        set_mock_user_token(&request);

        test::call_service(&app, request).await;

        let filename = format!("{filename_prefix}{filename_suffix}");
        let encoded_filename = urlencoding::encode(&filename);

        let request = test::TestRequest::get()
            .uri(&format!(
                "/package/{package_name}/{package_version}/path/src/{encoded_filename}",
            ))
            .to_request();

        let response = test::call_service(&app, request).await;

        assert!(response.headers().contains_key("content-type"));
        assert!(response.headers().contains_key("content-disposition"));
        assert_eq!(
            response.headers().get("content-type").unwrap(),
            "text/plain"
        );
        assert_eq!(
            response.headers().get("content-disposition").unwrap(),
            format!("attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded_filename}")
                .as_str()
        );

        package_folder.close()?;
        Ok(())
    }
}
