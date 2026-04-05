use serde::{Deserialize, Serialize};

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
pub struct Source {
    pub name: String,
    pub version: String,
}

#[derive(PartialEq, Eq, Debug, Serialize, Deserialize, Clone)]
#[serde(untagged)]
pub enum HelperSource {
    Source(Source),
    ShortSource(String),
}

impl From<HelperSource> for Source {
    fn from(helper_source: HelperSource) -> Self {
        match helper_source {
            HelperSource::Source(source) => source,
            HelperSource::ShortSource(source) => Source {
                name: source,
                version: "*".to_string(),
            },
        }
    }
}
