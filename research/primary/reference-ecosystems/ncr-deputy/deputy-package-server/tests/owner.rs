mod common;

#[cfg(test)]
mod tests {
    use crate::common::{set_mock_user_token, setup_package_server, upload_test_package};
    use actix_web::web::{delete, post};
    use actix_web::{
        test,
        web::{get, scope},
        App,
    };
    use anyhow::Result;
    use deputy_package_server::test::middleware::MockTokenMiddlewareFactory;
    use deputy_package_server::{
        routes::owner::{add_owner, delete_owner, get_all_owners},
        test::database::MockDatabase,
    };

    #[actix_web::test]
    async fn test_add_new_owner() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;

        let package_name = upload_test_package(&app_state).await.unwrap();

        let app = test::init_service(
            App::new().app_data(app_state).service(
                scope("/package").service(
                    scope("/{package_name}").service(
                        scope("/owner")
                            .route("", post().to(add_owner::<MockDatabase>))
                            .wrap(MockTokenMiddlewareFactory),
                    ),
                ),
            ),
        )
        .await;

        let request = test::TestRequest::post()
            .uri(&format!(
                "/package/{}/owner?email={}",
                package_name,
                "new-owner".to_string()
            ))
            .to_request();
        set_mock_user_token(&request);

        let response = test::call_service(&app, request).await;
        package_folder.close()?;
        assert!(response.status().is_success());
        Ok(())
    }

    #[actix_web::test]
    async fn test_list_owners() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let package_name = upload_test_package(&app_state).await.unwrap();

        let app =
            test::init_service(App::new().app_data(app_state).service(
                scope("/package").service(
                    scope("/{package_name}").service(
                        scope("/owner").route("", get().to(get_all_owners::<MockDatabase>)),
                    ),
                ),
            ))
            .await;

        let request = test::TestRequest::get()
            .uri(&format!("/package/{}/owner", package_name,))
            .to_request();

        let response = test::call_service(&app, request).await;
        let response_status = response.status();
        let result_json: serde_json::Value = test::read_body_json(response).await;
        let result = result_json.as_array().unwrap();

        package_folder.close()?;
        assert!(response_status.is_success());
        assert!(result.len() == 1);
        Ok(())
    }

    #[actix_web::test]
    async fn test_delete_owner() -> Result<()> {
        let (package_folder, app_state) = setup_package_server(None)?;
        let package_name = upload_test_package(&app_state).await.unwrap();

        let app = test::init_service(
            App::new().app_data(app_state).service(
                scope("/package").service(
                    scope("/{package_name}").service(
                        scope("/owner")
                            .route("", post().to(add_owner::<MockDatabase>))
                            .route("/{owner_email}", delete().to(delete_owner::<MockDatabase>))
                            .wrap(MockTokenMiddlewareFactory),
                    ),
                ),
            ),
        )
        .await;

        let second_owner_request = test::TestRequest::post()
            .uri(&format!(
                "/package/{}/owner?email={}",
                package_name,
                "new-owner".to_string()
            ))
            .to_request();
        set_mock_user_token(&second_owner_request);
        test::call_service(&app, second_owner_request).await;

        let request = test::TestRequest::delete()
            .uri(&format!(
                "/package/{}/owner/{}",
                package_name,
                "new-owner".to_string()
            ))
            .to_request();
        set_mock_user_token(&request);
        let response = test::call_service(&app, request).await;

        package_folder.close()?;
        assert!(response.status().is_success());
        Ok(())
    }
}
