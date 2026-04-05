use crate::constants::PACKAGE_TOML;
use crate::project::{Content, ContentType, Project};
use crate::{
    archiver::{self, ArchiveStreamer},
    project::Body,
};
use actix_http::error::PayloadError;
use actix_web::web::Bytes;
use anyhow::{anyhow, Result};
use base64::{engine::general_purpose, Engine};
use flate2::read::MultiGzDecoder;
use futures::{Stream, StreamExt};
use infer::archive::is_gz;
use pulldown_cmark::{html, Event, Options, Parser, Tag, TagEnd};
use scraper::{Html, Selector};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File},
    io::{copy, Read, Seek, SeekFrom, Write},
    ops::{Deref, DerefMut},
    path::{Path, PathBuf},
    pin::Pin,
};
use tar::Archive;
use tempfile::TempPath;
use tokio::fs::File as TokioFile;
use tokio_util::codec::{BytesCodec, FramedRead};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PackageMetadata {
    pub name: String,
    pub package_type: ContentType,
    pub version: String,
    pub description: String,
    pub license: String,
    pub readme_path: String,
    pub package_size: u64,
    pub categories: Option<Vec<String>>,
    pub checksum: String,
}

async fn process_image(
    url_str: &str,
    alt_text: &str,
    width: &str,
    package_path: &Path,
) -> Result<String> {
    if !url_str.starts_with("http") {
        let image_path = url_str.to_string();
        let mut archive = ArchiveStreamer::prepare_archive(package_path.to_path_buf())?;
        if let Some(mut image_stream) = ArchiveStreamer::try_new(&mut archive, image_path.into())? {
            let mut img_bytes = Vec::new();
            while let Some(bytes) = image_stream.next().await {
                let bytes =
                    bytes.map_err(|error| anyhow!("Failed to read image stream: {error}"))?;
                img_bytes.extend_from_slice(&bytes);
            }
            let img_base64 = general_purpose::STANDARD.encode(&img_bytes);
            Ok(format!(
                "<img src=\"data:image/png;base64,{}\" alt=\"{}\" width=\"{}\" />",
                img_base64, alt_text, width
            ))
        } else {
            Err(anyhow!("Failed to create image stream"))
        }
    } else {
        Ok(format!(
            "<img src=\"{}\" alt=\"{}\" width=\"{}\" />",
            url_str, alt_text, width
        ))
    }
}

async fn try_process_img_tag(html: &str, package_path: &Path) -> Result<Option<String>> {
    let element = Html::parse_fragment(html);
    let img_selector =
        Selector::parse("img").map_err(|error| anyhow!("Failed to parse selector: {error}"))?;

    if let Some(img_tag) = element.select(&img_selector).next() {
        let src = img_tag.value().attr("src").unwrap_or("").to_string();
        let alt = img_tag.value().attr("alt").unwrap_or("").to_string();
        let width = img_tag.value().attr("width").unwrap_or("").to_string();

        let processed_img_tag = process_image(&src, &alt, &width, package_path).await?;
        return Ok(Some(processed_img_tag));
    }

    Ok(None)
}

impl PackageMetadata {
    pub async fn readme_html(&self, package_base_path: PathBuf) -> Result<Option<String>> {
        let readme_path = self.readme_path.clone();
        let package_path_end = Package::normalize_file_path(&self.name, &self.version);
        let package_path = package_base_path.join(package_path_end);

        let mut archive = ArchiveStreamer::prepare_archive(package_path.clone())?;
        if let Some(mut archive_stream) =
            ArchiveStreamer::try_new(&mut archive, readme_path.clone().into())?
        {
            let mut readme_markdown_string = String::new();
            while let Some(bytes) = archive_stream.next().await {
                let bytes =
                    bytes.map_err(|error| anyhow!("Failed to read archive stream: {error}"))?;
                readme_markdown_string.push_str(&String::from_utf8(bytes.to_vec())?);
            }

            let mut options = Options::empty();
            options.insert(Options::ENABLE_TABLES);
            options.insert(Options::ENABLE_FOOTNOTES);
            options.insert(Options::ENABLE_TASKLISTS);
            options.insert(Options::ENABLE_STRIKETHROUGH);
            options.insert(Options::ENABLE_SMART_PUNCTUATION);
            options.insert(Options::ENABLE_HEADING_ATTRIBUTES);

            let parser = Parser::new_ext(&readme_markdown_string, options);
            let mut html_output = String::new();
            let mut buffer = String::new();

            let mut parsing_md_img = false;
            let mut md_img_alt_text = String::new();
            let mut md_img_src_url = String::new();

            for event in parser {
                match event {
                    Event::Start(Tag::Image { dest_url, .. }) => {
                        parsing_md_img = true;
                        md_img_src_url = dest_url.to_string();
                    }

                    Event::Text(text) if parsing_md_img => {
                        md_img_alt_text.push_str(&text);
                    }

                    Event::End(TagEnd::Image) => {
                        parsing_md_img = false;

                        let md_img_tag =
                            process_image(&md_img_src_url, &md_img_alt_text, "", &package_path)
                                .await?;
                        buffer.push_str(&md_img_tag);
                        md_img_alt_text.clear();
                        md_img_src_url.clear();
                    }

                    Event::Html(html) | Event::InlineHtml(html) => {
                        let processed_img_tag = try_process_img_tag(&html, &package_path).await?;
                        if let Some(processed_img_tag) = processed_img_tag {
                            buffer.push_str(&processed_img_tag);
                        };
                    }
                    _ => html::push_html(&mut buffer, std::iter::once(event)),
                }
            }

            html_output.push_str(&buffer);

            return Ok(Some(html_output));
        }
        Ok(None)
    }

    pub async fn from_stream(
        mut stream: impl Stream<Item = Result<Bytes, PayloadError>> + Unpin + 'static,
    ) -> Result<(Self, PackageStream)> {
        let mut bytes = Vec::new();
        let mut metadata_length: Option<u32> = None;
        let mut reminder = Vec::new();
        while let Some(chunk) = stream.next().await {
            let mut chunk = chunk?;
            if metadata_length.is_none() {
                if chunk.len() < 4 {
                    return Err(anyhow!(
                        "Chunk length is less than 4 bytes. Length: {:?}",
                        chunk.len()
                    ));
                }
                let mut u32_as_bytes = [0u8; 4];
                u32_as_bytes.copy_from_slice(&chunk[0..4]);
                metadata_length = Some(u32::from_le_bytes(u32_as_bytes));
                chunk = chunk.slice(4..);
            }
            if let Some(metadata_lenght) = metadata_length {
                if bytes.len() + chunk.len() < metadata_lenght as usize {
                    bytes.extend_from_slice(&chunk);
                } else if bytes.len() < metadata_lenght as usize {
                    let (last_metadata_bytes, first_file_bytes) =
                        chunk.split_at(metadata_lenght as usize - bytes.len());
                    bytes.extend_from_slice(last_metadata_bytes);
                    reminder.extend_from_slice(first_file_bytes);
                    break;
                } else {
                    break;
                }
            }
        }
        let metadata: PackageMetadata = serde_json::from_slice(&bytes)?;
        let reminder = vec![Ok(Bytes::from(reminder))];
        let new_body = Box::pin(futures::stream::iter(reminder));
        let stream = new_body.chain(stream).boxed_local();
        Ok((metadata, stream))
    }
}

#[derive(Debug)]
pub struct PackageFile(pub File, pub Option<TempPath>);

impl PackageFile {
    fn save(&self, save_path: &PathBuf) -> Result<()> {
        let package_folder_path = save_path
            .parent()
            .ok_or_else(|| anyhow!("Could not get parent path from save path: {:?}", save_path))?;
        fs::create_dir_all(package_folder_path)?;
        let original_path: PathBuf = self
            .1
            .as_ref()
            .ok_or_else(|| anyhow!("Temporary file path not found"))?
            .to_path_buf();

        fs::copy(original_path, save_path)?;
        Ok(())
    }

    #[cfg(feature = "test")]
    pub fn calculate_checksum(&mut self) -> Result<String> {
        let mut hasher = Sha256::new();
        copy(&mut self.0, &mut hasher)?;
        let hash_bytes = hasher.finalize();
        Ok(format!("{hash_bytes:x}",))
    }

    #[cfg(not(feature = "test"))]
    fn calculate_checksum(&mut self) -> Result<String> {
        let mut hasher = Sha256::new();
        copy(&mut self.0, &mut hasher)?;
        let hash_bytes = hasher.finalize();
        Ok(format!("{hash_bytes:x}",))
    }

    pub async fn from_stream(mut stream: PackageStream) -> Result<Self> {
        let mut file = tempfile::NamedTempFile::new()?;
        let mut file_size: Option<u64> = None;
        let mut intermediate_buffer: Vec<u8> = Vec::new();
        while let Some(chunk) = stream.next().await {
            let chunk = chunk?;
            let mut first = false;
            if file_size.is_none() {
                if chunk.len() <= 8 {
                    intermediate_buffer.append(&mut chunk.to_vec());
                } else {
                    intermediate_buffer = chunk.to_vec();
                }
                if intermediate_buffer.len() > 7 {
                    let mut u64_bytes = [0u8; 8];
                    u64_bytes.copy_from_slice(&intermediate_buffer[0..8]);
                    file_size = Some(u64::from_le_bytes(u64_bytes));
                    first = true;
                }
            }
            if file_size.is_some() {
                if first {
                    file.write_all(&intermediate_buffer[8..])?;
                } else {
                    file.write_all(&chunk)?;
                }
            }
        }
        file.flush()?;

        let new_handler = file.reopen()?;
        let temporary_path = file.into_temp_path();

        Ok(PackageFile(new_handler, Some(temporary_path)))
    }

    pub(crate) fn get_size(&self) -> Result<u64> {
        Ok(self.metadata()?.len())
    }
}

#[derive(Debug)]
pub struct Package {
    pub metadata: PackageMetadata,
    pub file: PackageFile,
}

impl Package {
    pub fn new(metadata: PackageMetadata, file: PackageFile) -> Self {
        Self { metadata, file }
    }

    pub fn normalize_file_path(name: &str, version: &str) -> PathBuf {
        PathBuf::from(name.to_lowercase()).join(version.to_lowercase())
    }

    pub fn save(&self, package_folder: &str) -> Result<()> {
        let path = PathBuf::from(package_folder).join(Package::normalize_file_path(
            &self.metadata.name,
            &self.metadata.version,
        ));
        self.file.save(&path)?;

        Ok(())
    }

    pub fn validate_checksum(&mut self) -> Result<()> {
        let calculated = self.file.calculate_checksum()?;
        if calculated != self.metadata.checksum {
            return Err(anyhow!(
                "Checksum mismatch. Calculated: {:?}, Expected: {:?}",
                calculated,
                self.metadata.checksum
            ));
        }
        Ok(())
    }

    pub fn validate_file_type(&mut self) -> Result<()> {
        let mut file_signature = [0; 4096];
        let file = &mut self.file.0;
        let bytes_read = file.read(&mut file_signature)?;

        file.seek(SeekFrom::Start(0))?;

        if is_gz(&file_signature[..bytes_read]) {
            Ok(())
        } else {
            Err(anyhow!("Invalid file type"))
        }
    }

    pub fn validate_archive_size(&mut self, max_archive_size: u64) -> Result<()> {
        let file = &mut self.file.0;

        if file.metadata()?.len() > max_archive_size {
            return Err(anyhow!("Archive exceeds maximum allowed size"));
        };

        let tarfile = MultiGzDecoder::new(file);
        let mut archive = Archive::new(tarfile);
        let mut total_uncompressed_size = 0;

        for entry_result in archive.entries()? {
            let mut entry = entry_result?;
            let entry_header_size = entry.header().size()?;
            total_uncompressed_size += entry_header_size;

            if total_uncompressed_size > max_archive_size {
                return Err(anyhow!("Uncompressed archive exceeds maximum allowed size"));
            }

            let mut buffer = [0; 32768];
            let mut entry_actual_size = 0;

            while let Ok(bytes_read) = entry.read(&mut buffer) {
                if bytes_read == 0 {
                    break;
                }

                entry_actual_size += bytes_read as u64;
                if entry_actual_size > entry_header_size {
                    return Err(anyhow!("Actual file size exceeds header size"));
                }
            }
        }

        self.file.0.seek(SeekFrom::Start(0))?;

        Ok(())
    }

    pub fn validate_consistency(&self) -> Result<()> {
        let mut package_file = &self.file.0;

        let decoder = MultiGzDecoder::new(package_file);
        let mut archive = Archive::new(decoder);
        let mut toml_bytes = Vec::new();

        for file in archive.entries()? {
            let mut file = file?;
            if file.path()?.to_str() == Some(PACKAGE_TOML) {
                file.read_to_end(&mut toml_bytes)?;
            }
        }
        package_file.rewind()?;

        let deserialized_toml: Project = toml::from_str(&String::from_utf8(toml_bytes)?)?;

        if self.metadata.name != deserialized_toml.package.name.to_lowercase() {
            return Err(anyhow!(
                "Name mismatch: expected '{}', found '{}'",
                self.metadata.name,
                deserialized_toml.package.name.to_lowercase()
            ));
        }
        if self.metadata.package_type != deserialized_toml.content.content_type {
            return Err(anyhow!(
                "Package type mismatch: expected '{:?}', found '{:?}'",
                self.metadata.package_type,
                deserialized_toml.content.content_type
            ));
        }
        if self.metadata.version != deserialized_toml.package.version {
            return Err(anyhow!(
                "Version mismatch: expected '{}', found '{}'",
                self.metadata.version,
                deserialized_toml.package.version
            ));
        }
        if self.metadata.description != deserialized_toml.package.description {
            return Err(anyhow!(
                "Description mismatch: expected '{}', found '{}'",
                self.metadata.description,
                deserialized_toml.package.description
            ));
        }
        if self.metadata.license != deserialized_toml.package.license {
            return Err(anyhow!(
                "License mismatch: expected '{}', found '{}'",
                self.metadata.license,
                deserialized_toml.package.license
            ));
        }
        if self.metadata.readme_path != deserialized_toml.package.readme {
            return Err(anyhow!(
                "Readme path mismatch: expected '{}', found '{}'",
                self.metadata.readme_path,
                deserialized_toml.package.readme
            ));
        }
        let actual_package_size = self.file.0.metadata()?.len();
        if self.metadata.package_size != actual_package_size {
            return Err(anyhow!(
                "Package size mismatch: expected '{}', found '{}'",
                self.metadata.package_size,
                actual_package_size
            ));
        }
        if self.metadata.categories != deserialized_toml.package.categories {
            return Err(anyhow!(
                "Categories mismatch: expected '{:?}', found '{:?}'",
                self.metadata.categories,
                deserialized_toml.package.categories
            ));
        }

        Ok(())
    }

    fn gather_metadata(toml_path: &Path, archive_path: &Path) -> Result<PackageMetadata> {
        let package_body = Body::create_from_toml(toml_path)?;
        let package_content = Content::create_from_toml(toml_path)?;
        let archive_file = File::open(archive_path)?;
        Ok(PackageMetadata {
            name: package_body.name.to_lowercase(),
            package_type: package_content.content_type,
            version: package_body.version,
            description: package_body.description,
            license: package_body.license,
            readme_path: package_body.readme,
            categories: package_body.categories,
            package_size: archive_file.metadata()?.len(),
            checksum: PackageFile(archive_file, None).calculate_checksum()?,
        })
    }

    pub fn from_file(package_toml_path: &PathBuf, compression: u32) -> Result<Self> {
        let archive_path = archiver::create_package(package_toml_path, compression)?;
        let metadata = Self::gather_metadata(package_toml_path, &archive_path)?;
        let file = File::open(&archive_path)?;
        let temp_path_option = Some(TempPath::from_path(archive_path));

        Ok(Package {
            metadata,
            file: PackageFile(file, temp_path_option),
        })
    }

    pub fn get_size(&self) -> Result<u64> {
        self.file.get_size()
    }

    pub async fn to_stream(self) -> Result<PackageStream> {
        let metadata_bytes = Vec::try_from(&self.metadata)?;
        if metadata_bytes.len() < 4 {
            return Err(anyhow!("Metadata is too short"));
        }

        let stream: PackageStream =
            Box::pin(futures::stream::iter(vec![Ok(Bytes::from(metadata_bytes))]));

        let archive_file = TokioFile::from(self.file.0);
        let archive_size = archive_file.metadata().await?.len();

        let stream = stream
            .chain(archive_size.to_stream())
            .chain(archive_file.to_stream());

        return Ok(stream.boxed_local());
    }
}

impl Deref for PackageFile {
    type Target = File;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

impl DerefMut for PackageFile {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.0
    }
}

impl TryFrom<&PackageMetadata> for Vec<u8> {
    type Error = anyhow::Error;

    fn try_from(index_info: &PackageMetadata) -> Result<Self> {
        let mut formatted_bytes = Vec::new();
        let string = serde_json::to_string(&index_info)?;
        let main_bytes = string.as_bytes();
        let length: u32 = main_bytes.len().try_into()?;

        formatted_bytes.extend_from_slice(&length.to_le_bytes());
        formatted_bytes.extend_from_slice(main_bytes);

        Ok(formatted_bytes)
    }
}

pub type PackageStream = Pin<Box<dyn Stream<Item = Result<Bytes, PayloadError>>>>;

pub trait Streamer {
    fn to_stream(self) -> PackageStream;
}

pub trait FromBytes
where
    Self: Sized,
{
    fn from_bytes(bytes: Bytes) -> Result<Self>;
}

impl Streamer for u64 {
    fn to_stream(self) -> PackageStream {
        let mut formatted_bytes = Vec::new();
        formatted_bytes.extend_from_slice(&self.to_le_bytes());
        let bytes = vec![Ok(Bytes::from(formatted_bytes))];
        Box::pin(futures::stream::iter(bytes))
    }
}

impl FromBytes for u64 {
    fn from_bytes(bytes: Bytes) -> Result<Self> {
        let mut length_bytes: [u8; 8] = Default::default();
        length_bytes.copy_from_slice(
            bytes
                .get(0..8)
                .ok_or_else(|| anyhow::anyhow!("Could not get bytes slice"))?,
        );
        Ok(u64::from_le_bytes(length_bytes))
    }
}

impl Streamer for TokioFile {
    fn to_stream(self) -> PackageStream {
        let stream = FramedRead::new(self, BytesCodec::new()).map(|bytes| match bytes {
            Ok(bytes) => Ok(bytes.freeze()),
            Err(err) => Err(PayloadError::Io(err)),
        });
        Box::pin(stream)
    }
}

#[cfg(test)]
mod tests {
    use crate::package::Package;
    use crate::test::TempArchive;
    use anyhow::{Ok, Result};
    use futures::StreamExt;
    use std::{fs::File, io::Read, path::PathBuf};
    use tempfile::tempdir;

    #[test]
    fn package_file_can_be_saved() -> Result<()> {
        let target_directory = tempdir()?;
        let package_folder = target_directory.path().to_str().unwrap().to_string();
        let temp_project = TempArchive::builder()
            .set_package_name("some-package-name")
            .build()?;
        let package: Package = (&temp_project).try_into()?;

        let test_name = "test-name";
        let test_version = "1.0.0";
        let expected_file_path: PathBuf = [
            package_folder.clone(),
            test_name.to_string(),
            test_version.to_string(),
        ]
        .iter()
        .collect();
        package.file.save(&expected_file_path)?;

        let mut created_file = File::open(expected_file_path)?;
        assert!(created_file.metadata().unwrap().is_file());

        let mut file_content = Vec::new();
        created_file.read_to_end(&mut file_content)?;

        target_directory.close()?;
        Ok(())
    }

    #[test]
    fn package_can_be_saved() -> Result<()> {
        let archive = TempArchive::builder()
            .set_package_name("some-package-name")
            .build()?;
        let test_package: Package = (&archive).try_into()?;
        let target_directory = tempdir()?;
        let package_folder = target_directory.path().to_str().unwrap().to_string();

        test_package.save(&package_folder)?;

        assert!(target_directory.path().join("some-package-name").exists());
        target_directory.close()?;
        Ok(())
    }

    #[test]
    fn metadata_is_converted_to_bytes() -> Result<()> {
        let archive = TempArchive::builder().build()?;
        let package: Package = (&archive).try_into()?;
        let metadata = package.metadata;
        let _metadata_bytes = Vec::try_from(&metadata)?;
        Ok(())
    }

    #[actix_web::test]
    async fn package_is_converted_to_stream() -> Result<()> {
        let archive = TempArchive::builder().build()?;
        let package: Package = (&archive).try_into()?;
        let mut byte_stream = package.to_stream().await?;
        let mut counter = 0;
        let mut bytes = Vec::new();
        while let Some(chunk) = byte_stream.next().await {
            let chunk = chunk.unwrap();
            bytes.append(&mut chunk.to_vec());
            counter += 1;
        }
        assert_eq!(counter, 3);
        Ok(())
    }
}
