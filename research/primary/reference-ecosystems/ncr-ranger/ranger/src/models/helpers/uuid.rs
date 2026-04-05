use diesel::{
    deserialize,
    deserialize::FromSql,
    mysql::{Mysql, MysqlValue},
    serialize,
    serialize::ToSql,
    serialize::{IsNull, Output},
    sql_types::Binary,
    AsExpression, FromSqlRow,
};
use serde::{Deserialize, Serialize};
use std::{
    fmt,
    fmt::{Display, Formatter},
    io::Write,
};

#[derive(Debug, Clone, Copy, FromSqlRow, AsExpression, Hash, Eq, PartialEq)]
#[diesel(sql_type = Binary)]
pub struct Uuid(pub uuid::Uuid);

impl Uuid {
    pub fn random() -> Self {
        Self(uuid::Uuid::new_v4())
    }
}

impl From<Uuid> for uuid::Uuid {
    fn from(s: Uuid) -> Self {
        s.0
    }
}

impl TryFrom<&str> for Uuid {
    type Error = uuid::Error;

    fn try_from(uuid_string: &str) -> Result<Self, uuid::Error> {
        Ok(Self(uuid::Uuid::parse_str(uuid_string)?))
    }
}

impl Serialize for Uuid {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.0.to_string())
    }
}

impl<'de> Deserialize<'de> for Uuid {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let uuid_string = String::deserialize(deserializer)?;
        match uuid::Uuid::parse_str(&uuid_string) {
            Ok(uuid) => Ok(Uuid(uuid)),
            Err(_) => Err(serde::de::Error::custom(format!(
                "Invalid UUID string: {uuid_string}"
            ))),
        }
    }
}

impl Display for Uuid {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl FromSql<Binary, Mysql> for Uuid {
    fn from_sql(bytes: MysqlValue) -> deserialize::Result<Self> {
        let value = <Vec<u8>>::from_sql(bytes)?;
        uuid::Uuid::from_slice(&value)
            .map(Uuid)
            .map_err(|e| e.into())
    }
}

impl ToSql<Binary, Mysql> for Uuid {
    fn to_sql(&self, out: &mut Output<Mysql>) -> serialize::Result {
        out.write_all(self.0.as_bytes())
            .map(|_| IsNull::No)
            .map_err(Into::into)
    }
}
