use crate::models::EmailStatusName;
use diesel::{
    deserialize,
    deserialize::FromSql,
    mysql::{Mysql, MysqlValue},
    serialize::{self},
    serialize::{IsNull, Output, ToSql},
    sql_types::Text,
};
use std::{
    fmt,
    fmt::{Display, Formatter},
    io::Write,
};

impl FromSql<Text, Mysql> for EmailStatusName {
    fn from_sql(bytes: MysqlValue) -> deserialize::Result<Self> {
        if let Ok(value) = <String>::from_sql(bytes) {
            return match value.as_str() {
                "pending" => Ok(EmailStatusName::Pending),
                "sent" => Ok(EmailStatusName::Sent),
                "failed" => Ok(EmailStatusName::Failed),
                _ => Err("Invalid email status name".into()),
            };
        }
        Err("Failed to parse email status name into string".into())
    }
}

impl Display for EmailStatusName {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl ToSql<Text, Mysql> for EmailStatusName {
    fn to_sql(&self, out: &mut Output<Mysql>) -> serialize::Result {
        let value = String::from(match self {
            EmailStatusName::Pending => "pending",
            EmailStatusName::Sent => "sent",
            EmailStatusName::Failed => "failed",
        });
        out.write_all(value.as_bytes())?;
        Ok(IsNull::No)
    }
}
