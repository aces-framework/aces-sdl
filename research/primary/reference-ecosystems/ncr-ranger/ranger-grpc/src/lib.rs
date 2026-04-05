pub mod pb {
    #![allow(clippy::derive_partial_eq_without_eq)]
    #![allow(non_camel_case_types)]

    tonic::include_proto!("_");
}

pub use pb::*;
