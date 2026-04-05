use diesel::{
    deserialize,
    deserialize::FromSql,
    mysql::{Mysql, MysqlValue},
    serialize,
    serialize::ToSql,
    serialize::{IsNull, Output},
    sql_types::Text,
    AsExpression, FromSqlRow,
};
use ranger_grpc::capabilities::DeployerType as GrpcDeployerType;
use serde::{Deserialize, Serialize};
use std::{
    fmt,
    fmt::{Display, Formatter},
    io::Write,
};

#[derive(Debug, Clone, Copy, FromSqlRow, AsExpression, Hash, Eq, PartialEq)]
#[diesel(sql_type = Text)]
pub struct DeployerType(pub GrpcDeployerType);

impl Serialize for DeployerType {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        let value = match self.0 {
            GrpcDeployerType::Switch => "switch",
            GrpcDeployerType::Template => "template",
            GrpcDeployerType::VirtualMachine => "virtual_machine",
            GrpcDeployerType::Feature => "feature",
            GrpcDeployerType::Condition => "condition",
            GrpcDeployerType::Inject => "inject",
            GrpcDeployerType::EventInfo => "event_info",
            GrpcDeployerType::DeputyQuery => "deputy_query",
        };
        serializer.serialize_str(value)
    }
}

impl<'de> Deserialize<'de> for DeployerType {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let type_string = String::deserialize(deserializer)?;
        match type_string.as_str() {
            "switch" => Ok(DeployerType(GrpcDeployerType::Switch)),
            "template" => Ok(DeployerType(GrpcDeployerType::Template)),
            "virtual_machine" => Ok(DeployerType(GrpcDeployerType::VirtualMachine)),
            "feature" => Ok(DeployerType(GrpcDeployerType::Feature)),
            "condition" => Ok(DeployerType(GrpcDeployerType::Condition)),
            "inject" => Ok(DeployerType(GrpcDeployerType::Inject)),
            "event_info" => Ok(DeployerType(GrpcDeployerType::EventInfo)),
            "deputy_query" => Ok(DeployerType(GrpcDeployerType::DeputyQuery)),
            _ => Err(serde::de::Error::custom(format!(
                "Invalid deployer type: {type_string}"
            ))),
        }
    }
}

impl FromSql<Text, Mysql> for DeployerType {
    fn from_sql(bytes: MysqlValue) -> deserialize::Result<Self> {
        if let Ok(value) = <String>::from_sql(bytes) {
            return match value.as_str() {
                "switch" => Ok(DeployerType(GrpcDeployerType::Switch)),
                "template" => Ok(DeployerType(GrpcDeployerType::Template)),
                "virtual_machine" => Ok(DeployerType(GrpcDeployerType::VirtualMachine)),
                "feature" => Ok(DeployerType(GrpcDeployerType::Feature)),
                "condition" => Ok(DeployerType(GrpcDeployerType::Condition)),
                "inject" => Ok(DeployerType(GrpcDeployerType::Inject)),
                "event_info" => Ok(DeployerType(GrpcDeployerType::EventInfo)),
                "deputy_query" => Ok(DeployerType(GrpcDeployerType::DeputyQuery)),
                _ => Err("Invalid deployer type".into()),
            };
        }
        Err("Failed to parse deployer type into string".into())
    }
}

impl Display for DeployerType {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl ToSql<Text, Mysql> for DeployerType {
    fn to_sql(&self, out: &mut Output<Mysql>) -> serialize::Result {
        let value = String::from(match self {
            DeployerType(GrpcDeployerType::Switch) => "switch",
            DeployerType(GrpcDeployerType::Template) => "template",
            DeployerType(GrpcDeployerType::VirtualMachine) => "virtual_machine",
            DeployerType(GrpcDeployerType::Feature) => "feature",
            DeployerType(GrpcDeployerType::Condition) => "condition",
            DeployerType(GrpcDeployerType::Inject) => "inject",
            DeployerType(GrpcDeployerType::EventInfo) => "event_info",
            DeployerType(GrpcDeployerType::DeputyQuery) => "deputy_query",
        });
        out.write_all(value.as_bytes())?;
        Ok(IsNull::No)
    }
}
