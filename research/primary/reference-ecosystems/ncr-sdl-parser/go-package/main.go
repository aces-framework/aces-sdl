package sdl_parser

/*
#cgo CFLAGS: -I/usr/include/sdl-parser
#cgo LDFLAGS: -L/usr/lib/sdl-parser -lsdl_parser
#include <stdlib.h>
#include <sdl_parser.h>
*/
import "C"

import (
	"encoding/json"
	"errors"
)

func ParseSDL(sdlString string) (map[string]interface{}, error) {
	cSDLString := C.CString(sdlString)
	responsePointer := C.parse_sdl_generate(cSDLString)
	defer C.parse_sdl_free(responsePointer)

	if responsePointer != nil {
		responseString := C.GoString(responsePointer)
		var response map[string]interface{}
		json.Unmarshal([]byte(responseString), &response)
		if response["status"] == "ERROR" {
			return nil, errors.New(response["errorMessage"].(string))
		}
		return response["result"].(map[string]interface{}), nil
	}
	return nil, errors.New("failed to parse")
}
