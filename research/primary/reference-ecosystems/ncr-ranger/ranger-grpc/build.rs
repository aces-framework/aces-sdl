use std::path::PathBuf;
use std::{env, fs};
use tonic_build::configure;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let out_dir = env::var_os("OUT_DIR").unwrap();
    let proto_path = PathBuf::from("grpc-proto");
    let proto_path_string = proto_path.to_str().unwrap();

    let proto_files = fs::read_dir(proto_path.join("src"))
        .expect("Failed to read directory")
        .filter_map(|entry| {
            let entry = entry.expect("Failed to read directory entry");
            if entry.path().extension()? == "proto" {
                Some(entry.path().to_str().unwrap().to_string())
            } else {
                None
            }
        })
        .collect::<Vec<_>>();

    configure()
        .emit_rerun_if_changed(true)
        .out_dir(out_dir)
        .compile(&proto_files, &[proto_path_string])?;

    Ok(())
}
