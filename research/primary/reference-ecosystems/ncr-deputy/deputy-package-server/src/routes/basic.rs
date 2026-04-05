use actix_web::{get, HttpResponse};

const PACKAGE_VERSION: &str = env!("CARGO_PKG_VERSION");

#[get("status")]
pub async fn status() -> HttpResponse {
    HttpResponse::Ok().body("OK")
}

#[get("version")]
pub async fn version() -> HttpResponse {
    HttpResponse::Ok().body(PACKAGE_VERSION)
}
