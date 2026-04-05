use anyhow::Result;
use libc::c_char;
use sdl_parser::{parse_sdl as parse_native_sdl, Scenario};
use serde::{Deserialize, Serialize};
use serde_json::{json, to_string};
use std::ffi::{CStr, CString};
use std::ptr;

#[derive(Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
enum Status {
    Success,
    Error,
}

#[derive(Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Response {
    status: Status,
    result: Option<Scenario>,
    error_message: Option<String>,
}

unsafe fn pointer_to_string<'a>(raw_pointer: *const c_char) -> Result<&'a str> {
    let raw = CStr::from_ptr(raw_pointer);
    Ok(raw.to_str()?)
}

/// # Safety
///
/// This function should only be called with a string pointer. In case of input being a null
/// pointer this function will also return a null pointer
#[no_mangle]
pub unsafe extern "C" fn parse_sdl_generate(sdl_string_pointer: *const c_char) -> *mut c_char {
    if sdl_string_pointer.is_null() {
        return ptr::null_mut();
    }

    if let Ok(sdl_string) = pointer_to_string(sdl_string_pointer) {
        let json_error_response = json!({
            "status": "ERROR",
            "errorMessage": "failed to serialize response to JSON"
        })
        .to_string();

        let response = match parse_native_sdl(sdl_string) {
            Ok(sld_schema) => {
                let success_response = Response {
                    status: Status::Success,
                    result: Some(sld_schema),
                    error_message: None,
                };
                to_string(&success_response).map_or(json_error_response, |result| result)
            }
            Err(err) => {
                let error_response = Response {
                    status: Status::Error,
                    result: None,
                    error_message: Some(err.to_string()),
                };
                to_string(&error_response).map_or(json_error_response, |result| result)
            }
        };
        if let Ok(c_str_response) = CString::new(response) {
            return c_str_response.into_raw();
        }
        return ptr::null_mut();
    }

    ptr::null_mut()
}

/// # Safety
///
/// This function should only be called with a string pointer. In case of input being a null
/// pointer this function will do nothing and just return
#[no_mangle]
pub unsafe extern "C" fn parse_sdl_free(sdl_string: *mut c_char) {
    if sdl_string.is_null() {
        return;
    }
    drop(CString::from_raw(sdl_string));
}
