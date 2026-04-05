use crate::models::ElementStatus;
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

impl FromSql<Text, Mysql> for ElementStatus {
    fn from_sql(bytes: MysqlValue) -> deserialize::Result<Self> {
        if let Ok(value) = <String>::from_sql(bytes) {
            return match value.as_str() {
                "ongoing" => Ok(ElementStatus::Ongoing),
                "success" => Ok(ElementStatus::Success),
                "failed" => Ok(ElementStatus::Failed),
                "removed" => Ok(ElementStatus::Removed),
                "removefailed" => Ok(ElementStatus::RemoveFailed),
                "conditionSuccess" => Ok(ElementStatus::ConditionSuccess),
                "conditionPolling" => Ok(ElementStatus::ConditionPolling),
                "conditionClosed" => Ok(ElementStatus::ConditionClosed),
                "conditionWarning" => Ok(ElementStatus::ConditionWarning),
                _ => Err("Invalid element status".into()),
            };
        }
        Err("Failed to parse element status into string".into())
    }
}

impl Display for ElementStatus {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl ToSql<Text, Mysql> for ElementStatus {
    fn to_sql(&self, out: &mut Output<Mysql>) -> serialize::Result {
        let value = String::from(match self {
            ElementStatus::Ongoing => "ongoing",
            ElementStatus::Success => "success",
            ElementStatus::Failed => "failed",
            ElementStatus::Removed => "removed",
            ElementStatus::RemoveFailed => "removefailed",
            ElementStatus::ConditionSuccess => "conditionSuccess",
            ElementStatus::ConditionPolling => "conditionPolling",
            ElementStatus::ConditionClosed => "conditionClosed",
            ElementStatus::ConditionWarning => "conditionWarning",
        });
        out.write_all(value.as_bytes())?;
        Ok(IsNull::No)
    }
}
