mod common;

#[cfg(test)]
mod tests {
    use crate::common::BodyTest;
    use actix_web::{body::to_bytes, test, App};
    use deputy_package_server::routes::basic::{status, version};
    use semver::Version;

    #[actix_web::test]
    async fn test_status() {
        let app = test::init_service(App::new().service(status)).await;
        let request = test::TestRequest::get().uri("/status").to_request();
        let response = test::call_service(&app, request).await;
        assert!(response.status().is_success());
    }

    #[actix_web::test]
    async fn test_version() {
        let app = test::init_service(App::new().service(version)).await;
        let request = test::TestRequest::get().uri("/version").to_request();
        let response = test::call_service(&app, request).await;
        assert!(response.status().is_success());
        let body = to_bytes(response.into_body()).await.unwrap();
        let version_string = body.as_str();
        Version::parse(version_string).unwrap();
    }
}
