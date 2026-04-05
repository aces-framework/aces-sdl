use crate::models::OrderStatus;
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

impl FromSql<Text, Mysql> for OrderStatus {
    fn from_sql(bytes: MysqlValue) -> deserialize::Result<Self> {
        if let Ok(value) = <String>::from_sql(bytes) {
            return match value.as_str() {
                "draft" => Ok(OrderStatus::Draft),
                "review" => Ok(OrderStatus::Review),
                "inprogress" => Ok(OrderStatus::InProgress),
                "ready" => Ok(OrderStatus::Ready),
                "finished" => Ok(OrderStatus::Finished),
                _ => Err("Invalid element status".into()),
            };
        }
        Err("Failed to parse element status into string".into())
    }
}

impl Display for OrderStatus {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl ToSql<Text, Mysql> for OrderStatus {
    fn to_sql(&self, out: &mut Output<Mysql>) -> serialize::Result {
        let value = String::from(match self {
            OrderStatus::Draft => "draft",
            OrderStatus::InProgress => "inprogress",
            OrderStatus::Review => "review",
            OrderStatus::Ready => "ready",
            OrderStatus::Finished => "finished",
        });
        out.write_all(value.as_bytes())?;
        Ok(IsNull::No)
    }
}
