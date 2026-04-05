use crate::{
    commands::{InfoOptions, ListOptions},
    constants::endpoints::PACKAGE_UPLOAD_PATH,
    helpers::create_file_from_stream,
};
use anyhow::{anyhow, Error, Ok, Result};
use awc::{http::header, Client as ActixWebClient};
use deputy_library::{
    package::PackageStream,
    rest::{OwnerRest, PackageWithVersionsRest, PackagesWithVersionsAndPagesRest, VersionRest},
};
use futures::StreamExt;
use log::error;
use qstring::QString;
use std::str::from_utf8;
use url::Url;

pub struct Client {
    client: ActixWebClient,
    api_base_url: Url,
    token: Option<String>,
}

impl Client {
    pub fn try_new(api_base_url: String, token: Option<String>) -> Result<Self> {
        let token = token.map(|token| format!("Bearer {}", token));
        Ok(Self {
            client: ActixWebClient::new(),
            api_base_url: Url::parse(&api_base_url)?,
            token,
        })
    }

    fn add_token_to_request(&self, request: &mut awc::ClientRequest) -> Result<()> {
        let token = self
            .token
            .clone()
            .ok_or_else(|| anyhow!("No login token found"))?;

        let headers = request.headers_mut();
        headers.insert(
            header::AUTHORIZATION,
            header::HeaderValue::from_str(&token)?,
        );
        Ok(())
    }

    fn response_to_error(message: &str, payload: Vec<u8>) -> Result<Error> {
        let error_message = format!("{message}: {}", from_utf8(&payload)?);
        error!("{error_message}");
        Ok(anyhow!(error_message))
    }

    pub async fn upload_package(&self, stream: PackageStream, timeout: u64) -> Result<()> {
        let post_uri = self.api_base_url.join(PACKAGE_UPLOAD_PATH)?;
        let mut client_request = self.client.post(post_uri.to_string());
        self.add_token_to_request(&mut client_request)?;

        let mut response = client_request
            .timeout(std::time::Duration::from_secs(timeout))
            .send_stream(stream)
            .await
            .map_err(|error| anyhow!("Failed to upload package: {:?}", error))?;

        if response.status().is_success() {
            return Ok(());
        }

        Err(Client::response_to_error(
            "Failed to upload package",
            response.body().await?.to_vec(),
        )?)
    }

    pub async fn download_package(&self, name: &str, version: &str, file_path: &str) -> Result<()> {
        let get_uri = self
            .api_base_url
            .join("api/v1/package/")?
            .join(&format!("{name}/"))?
            .join(&format!("{version}/"))?
            .join("download")?;
        let mut response = self
            .client
            .get(get_uri.to_string())
            .send()
            .await
            .map_err(|error| anyhow!("Failed to download package: {:?}", error))?;
        if response.status().is_success() {
            create_file_from_stream(&mut response, file_path).await?;
            return Ok(());
        }

        Err(Client::response_to_error(
            "Failed to download package",
            response.body().await?.to_vec(),
        )?)
    }

    pub async fn get_package_version(&self, name: String, version: String) -> Result<VersionRest> {
        let get_uri = self
            .api_base_url
            .join("api/v1/package/")?
            .join(&format!("{name}/"))?
            .join(&version)?;
        let mut response = self
            .client
            .get(get_uri.to_string())
            .send()
            .await
            .map_err(|error| anyhow!("Failed to fetch package metadata: {:?}", error))?;
        if response.status().is_success() {
            let mut body = Vec::new();
            while let Some(chunk) = response.next().await {
                let chunk = chunk.map_err(|e| anyhow!("Failed to read chunk: {:?}", e))?;
                body.extend_from_slice(&chunk);
            }
            let version_rest: VersionRest = serde_json::from_slice(&body)?;
            return Ok(version_rest);
        }

        Err(Client::response_to_error(
            "Failed to fetch package metadata",
            response.body().await?.to_vec(),
        )?)
    }

    pub async fn get_latest_matching_package(
        &self,
        name: &str,
        version_requirement: &str,
    ) -> Result<VersionRest> {
        let mut get_uri = self.api_base_url.join("api/v1/package/")?.join(name)?;
        get_uri.set_query(Some(
            QString::new(vec![("version_requirement", version_requirement)])
                .to_string()
                .as_str(),
        ));

        let mut response = self
            .client
            .get(get_uri.to_string())
            .send()
            .await
            .map_err(|error| anyhow!("Failed to fetch packages: {:?}", error))?;
        if response.status().is_success() {
            let mut body = Vec::new();
            while let Some(chunk) = response.next().await {
                let chunk = chunk.map_err(|e| anyhow!("Failed to read chunk: {:?}", e))?;
                body.extend_from_slice(&chunk);
            }

            let packages: Vec<VersionRest> = serde_json::from_slice(&body)?;
            if let Some(matching_package) = VersionRest::get_latest_package(packages)? {
                return Ok(matching_package);
            }
            return Err(anyhow!(
                "No packages with {name} found matching version requirement {version_requirement}",
            ));
        }

        Err(Client::response_to_error(
            "Failed to fetch packages",
            response.body().await?.to_vec(),
        )?)
    }

    pub async fn validate_version(&self, name: String, version: String) -> Result<()> {
        let get_uri = self.api_base_url.join("api/v1/package/")?.join(&name)?;

        let mut response = self
            .client
            .get(get_uri.to_string())
            .timeout(std::time::Duration::from_secs(100))
            .send()
            .await
            .map_err(|error| anyhow!("Failed to validate package version: {:?}", error))?;

        match response.status() {
            awc::http::StatusCode::NOT_FOUND => Ok(()),
            awc::http::StatusCode::OK => {
                let mut body = Vec::new();
                while let Some(chunk) = response.next().await {
                    let chunk = chunk.map_err(|e| anyhow!("Failed to read chunk: {:?}", e))?;
                    body.extend_from_slice(&chunk);
                }
                let packages: Vec<VersionRest> = serde_json::from_slice(&body)?;
                if let Some(existing) = VersionRest::is_latest_version(&version, packages)? {
                    return Err(anyhow!(
                        "Package version \"{version}\" is not newer than the current version. Latest version is \"{existing}\"",
                    ));
                }
                Ok(())
            }
            _ => Err(Client::response_to_error(
                "Package version error",
                response.body().await?.to_vec(),
            )?),
        }
    }

    pub async fn yank_version(
        &self,
        name: &str,
        version: &str,
        set_yank: &str,
    ) -> Result<VersionRest> {
        let put_uri = self
            .api_base_url
            .join("api/v1/package/")?
            .join(format!("{name}/{version}/yank/{set_yank}").as_str())?;
        let mut client_request = self
            .client
            .put(put_uri.to_string())
            .timeout(std::time::Duration::from_secs(100));
        self.add_token_to_request(&mut client_request)?;
        let mut response = client_request
            .send()
            .await
            .map_err(|error| anyhow!("Failed to yank version: {:?}", error))?;

        if response.status().is_success() {
            let mut body = Vec::new();
            while let Some(chunk) = response.next().await {
                let chunk = chunk.map_err(|e| anyhow!("Failed to read chunk: {:?}", e))?;
                body.extend_from_slice(&chunk);
            }
            let version_rest: VersionRest = serde_json::from_slice(&body)?;
            return Ok(version_rest);
        }

        Err(Client::response_to_error(
            "Failed to yank version",
            response.body().await?.to_vec(),
        )?)
    }

    pub async fn add_owner(&self, package_name: &str, owner_email: &str) -> Result<()> {
        let uri = self
            .api_base_url
            .join("api/v1/package/")?
            .join(format!("{package_name}/owner?email={owner_email}").as_str())?;
        let mut client_request = self
            .client
            .post(uri.to_string())
            .timeout(std::time::Duration::from_secs(100));
        self.add_token_to_request(&mut client_request)?;

        let mut response = client_request
            .send()
            .await
            .map_err(|error| anyhow!("Failed to add owner: {:?}", error))?;

        if response.status().is_success() {
            return Ok(());
        }

        Err(Client::response_to_error(
            "Failed to add owner",
            response.body().await?.to_vec(),
        )?)
    }

    pub async fn delete_owner(&self, package_name: &str, owner_email: &str) -> Result<()> {
        let uri = self
            .api_base_url
            .join("api/v1/package/")?
            .join(format!("{package_name}/owner/{owner_email}").as_str())?;
        let mut client_request = self
            .client
            .delete(uri.to_string())
            .timeout(std::time::Duration::from_secs(100));
        self.add_token_to_request(&mut client_request)?;

        let mut response = client_request
            .send()
            .await
            .map_err(|error| anyhow!("{:?}", error))?;

        if response.status().is_success() {
            return Ok(());
        }

        Err(Client::response_to_error(
            "Failed to delete owner",
            response.body().await?.to_vec(),
        )?)
    }

    pub async fn list_owners(&self, package_name: &str) -> Result<Vec<String>> {
        let uri = self
            .api_base_url
            .join("api/v1/package/")?
            .join(format!("{package_name}/owner").as_str())?;
        let client_request = self
            .client
            .get(uri.to_string())
            .timeout(std::time::Duration::from_secs(100));

        let mut response = client_request
            .send()
            .await
            .map_err(|error| anyhow!("{:?}", error))?;

        if response.status().is_success() {
            let mut body = Vec::new();
            while let Some(chunk) = response.next().await {
                let chunk = chunk.map_err(|e| anyhow!("Failed to read chunk: {:?}", e))?;
                body.extend_from_slice(&chunk);
            }
            let owners: Vec<OwnerRest> = serde_json::from_slice(&body)?;
            let owner_emails: Vec<String> =
                owners.iter().map(|owner| owner.email.clone()).collect();

            return Ok(owner_emails);
        }

        Err(Client::response_to_error(
            "Failed to list owners",
            response.body().await?.to_vec(),
        )?)
    }

    pub async fn list_packages(
        &self,
        options: &ListOptions,
    ) -> Result<Vec<PackageWithVersionsRest>> {
        let mut base_get_uri = self.api_base_url.join("api/v1/package")?;

        base_get_uri
            .query_pairs_mut()
            .append_pair("paginated", "false");

        if let Some(search_term) = &options.search_term {
            base_get_uri
                .query_pairs_mut()
                .append_pair("search_term", search_term);
        }
        if let Some(package_type) = &options.package_type {
            base_get_uri
                .query_pairs_mut()
                .append_pair("type", package_type);
        }
        if let Some(category) = &options.category {
            base_get_uri
                .query_pairs_mut()
                .append_pair("categories", category);
        }

        let mut response = self
            .client
            .get(base_get_uri.to_string())
            .send()
            .await
            .map_err(|error| anyhow!("Failed to list packages: {:?}", error))?;

        if response.status().is_success() {
            let mut body = Vec::new();
            while let Some(chunk) = response.next().await {
                let chunk = chunk.map_err(|e| anyhow!("Failed to read chunk: {:?}", e))?;
                body.extend_from_slice(&chunk);
            }

            let packages_with_versions_and_pages: PackagesWithVersionsAndPagesRest =
                serde_json::from_slice(&body)?;
            return Ok(packages_with_versions_and_pages.packages);
        }

        Err(Client::response_to_error(
            "Failed to list packages",
            response.body().await?.to_vec(),
        )?)
    }

    pub async fn package_info(
        &self,
        options: &InfoOptions,
    ) -> Result<Vec<PackageWithVersionsRest>> {
        let mut base_get_uri = self.api_base_url.join("api/v1/package")?;

        base_get_uri
            .query_pairs_mut()
            .append_pair("search_term", &options.search_term);

        let mut response = self
            .client
            .get(base_get_uri.to_string())
            .send()
            .await
            .map_err(|error| anyhow!("Failed to get package info: {:?}", error))?;

        if response.status().is_success() {
            let mut body = Vec::new();
            while let Some(chunk) = response.next().await {
                let chunk = chunk.map_err(|e| anyhow!("Failed to read chunk: {:?}", e))?;
                body.extend_from_slice(&chunk);
            }
            let packages_with_versions_and_pages: PackagesWithVersionsAndPagesRest =
                serde_json::from_slice(&body)?;
            return Ok(packages_with_versions_and_pages.packages);
        }

        Err(Client::response_to_error(
            "Failed to get package info",
            response.body().await?.to_vec(),
        )?)
    }
}
