use sdl_parser::parse_sdl;
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn parse_and_verify_sdl(sdl_string: &str) -> Result<String, String> {
    let result = parse_sdl(sdl_string);
    match result {
        Ok(scenario) => match serde_json::to_string(&scenario) {
            Ok(json) => Ok(json),
            Err(err) => Err(err.to_string()),
        },
        Err(err) => Err(err.to_string()),
    }
}
