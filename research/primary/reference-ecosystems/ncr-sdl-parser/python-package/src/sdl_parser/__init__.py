import sys, ctypes
from ctypes import c_void_p, c_char_p
import json

prefix = {'win32': ''}.get(sys.platform, 'lib')
extension = {'darwin': '.dylib', 'win32': '.dll'}.get(sys.platform, '.so')
library = ctypes.cdll.LoadLibrary(prefix + "sdl_parser" + extension)

library.parse_sdl_generate.argtypes = (c_char_p, )
library.parse_sdl_generate.restype = c_void_p

library.parse_sdl_free.argtypes = (c_void_p, )

class SDLLibraryParsingError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

def handle_response_json(sdl_result_json):
  result = json.loads(sdl_result_json)
  if result['status'] == 'SUCCESS':
    return result['result']
  else:
    raise SDLLibraryParsingError(result['errorMessage'])

def parse_sdl(string):
    pointer = library.parse_sdl_generate(string.encode('utf-8'))
    try:
        string_result = ctypes.cast(pointer, ctypes.c_char_p).value.decode('utf-8')
        return handle_response_json(string_result)
    finally:
        library.parse_sdl_free(pointer)
