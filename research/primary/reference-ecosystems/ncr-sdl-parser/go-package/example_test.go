package sdl_parser

import (
	"fmt"
)

func ExampleParseSDL() {
	
	fmt.Println(ParseSDL(`
 name: test-scenario`))
 
	// Output:
	// map[map[description:<nil> infrastructure:<nil> name:test-scenario]] <nil>

}
