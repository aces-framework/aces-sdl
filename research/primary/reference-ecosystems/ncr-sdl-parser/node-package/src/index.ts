import { Library } from 'ffi-napi';

const sdlLibrary = Library('libsdl_parser', {
  parse_sdl_generate: ['char *', ['string']],
  parse_sdl_free: ['void', ['char *']],
});

export default function parseSDL(sdlString: string): Object | null {
  const responsePointer = sdlLibrary.parse_sdl_generate(sdlString) as any;
  let possibleErrorDuringExecution = null;
  try {
    const responseString = responsePointer.readCString();
    const response: any = JSON.parse(responseString);
    if (response.status === 'SUCCESS') {
      return response.result;
    }
    throw new Error(response.errorMessage);
  } catch (e) {
    possibleErrorDuringExecution = e;
  } finally {
    sdlLibrary.parse_sdl_free(responsePointer);
  }

  if (possibleErrorDuringExecution) {
    throw possibleErrorDuringExecution;
  }
  return null;
}
