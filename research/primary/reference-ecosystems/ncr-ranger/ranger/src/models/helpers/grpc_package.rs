use ranger_grpc::Package;
use serde::Serialize;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SerializableGrpcPackage {
    pub name: String,
    pub version: String,
    pub package_type: String,
}

impl From<Package> for SerializableGrpcPackage {
    fn from(package: Package) -> Self {
        Self {
            name: package.name,
            version: package.version,
            package_type: package.r#type,
        }
    }
}
