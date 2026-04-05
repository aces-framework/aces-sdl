<a href="https://cr14.ee">
    <img src="assets/logos/CR14-logo.svg" alt="CR14 Logo" width="100" height="100">
</a>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://eas.ee">
    <img src="assets/logos/eas-logo.svg" alt="EAS Logo" width="100" height="100">
</a>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://taltech.ee">
    <img src="assets/logos/Taltech-logo.svg" alt="Taltech Logo" width="100" height="100">
</a>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://eeagrants.org">
    <img src="assets/logos/ng.png" alt="NG Logo" width="100" height="100">
</a>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://ntnu.edu">
    <img src="assets/logos/NTNU-logo.svg" alt="NTNU Logo" width="100" height="100">
</a>

# SDL parser library

This library handles parsing SDL input for different programming libraries and environments


- Main parser is written in Rust and offers Rust native library
- `sdl-parser-export` is dynamic library written in Rust, which offers access to parsing logic over Foreign-Function-Interface
- Wrapper libraries offer easy access in mainstream programming libraries, which abstract the logic of calling functions over FFI
  - PyPi library
  - npm library (node)

## Setup

In order to use wrapper libraries, dynamic libraries must be installed on the system.

Once OCR apt repostiory is installed, this can be done
by executing

`sudo apt install libsdl-parser`

## Adding tests

In order to add test snapshots, it is first needed to run the test(s), which creates the new snapshots. Then the snapshots need to be reviewed with

`cargo insta review`

and new ones have to be approved, so the snapshot doesn't have ".new" in the end anymore.

If the insta crate isn't installed, then just execute

`cargo install cargo-insta`
