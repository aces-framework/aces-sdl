<a href="https://cr14.ee">
    <img src="../assets/logos/CR14-logo.svg" alt="CR14 Logo" width="100" height="100">
</a>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://eas.ee">
    <img src="../assets/logos/eas-logo.svg" alt="EAS Logo" width="100" height="100">
</a>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://taltech.ee">
    <img src="..//assets/logos/Taltech-logo.svg" alt="Taltech Logo" width="100" height="100">
</a>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://eeagrants.org">
    <img src="../assets/logos/ng.png" alt="NG Logo" width="100" height="100">
</a>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://ntnu.edu">
    <img src="..//assets/logos/NTNU-logo.svg" alt="NTNU Logo" width="100" height="100">
</a>

# SDL parser

The SDL parser is a Rust tool designed for parsing Scenario Defined Language files and is a part of Open Cyber Range suite. The SDL parser tool can be used to extract this information from SDL files and convert it into a format that can be used by other tools. With its advanced memory management and error handling features, the SDL parser offers fast parsing times and low memory usage, making it ideal for modern applications that require speed and efficiency in security analysis. If you're looking to integrate SDL files into your Rust project for security analysis, the SDL parser is an essential tool that simplifies the process and ensures accurate and reliable security assessments.

## Documentation

- [**The SDL Reference Guide**](https://documentation.opencyberrange.ee/docs/sdl-reference-guide/sdl)

## Getting Started

To use the SDL parser, you'll need to add it as a dependency to your project. You can do this by adding the following line to your Cargo.toml file:

```
[dependencies]
sdl-parser = "0.16"
```

After adding the dependency, you can use the SDL parser in your Rust code:

```
use sdl_parser::parse_sdl;

fn main() {
        let sdl = r#"
            name: test-scenario
            description: some-description
        "#;
        let scenario = parse_sdl(sdl).unwrap();
        assert_eq!(scenario.name, "test-scenario")
}
```

## Performance

The SDL parser tool is designed for optimal performance. It uses Rust's advanced memory management and error handling features to provide fast parsing times and low memory usage.

## Contributions

Contributions to the SDL parser project are welcome and encouraged. If you have any bug reports or feature requests, please file them in the GitHub issues tracker. If you'd like to contribute code, please submit a pull request.

## License

The SDL parser tool is released under the MIT License.

## Contact Information

If you have any questions or concerns about the SDL Parser tool, please contact us at developers@cr14.ee
