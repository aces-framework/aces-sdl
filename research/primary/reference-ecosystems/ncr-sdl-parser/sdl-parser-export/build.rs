extern crate cbindgen;

use cbindgen::{Config, Language::C};
use std::env;
use std::path::PathBuf;

fn main() {
    let crate_dir = env::var("CARGO_MANIFEST_DIR").unwrap();

    let package_name = "sdl_parser";
    let output_file = target_dir()
        .join(format!("{}.h", package_name))
        .display()
        .to_string();

    let config = Config {
        language: C,
        ..Default::default()
    };

    cbindgen::generate_with_config(crate_dir, config)
        .unwrap()
        .write_to_file(output_file);
}

fn target_dir() -> PathBuf {
    let mut path_buffer = PathBuf::from(env::var("OUT_DIR").unwrap());
    path_buffer.push("..");
    path_buffer.push("..");
    path_buffer.push("..");
    path_buffer
}
