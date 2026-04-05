# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.245.2/containers/rust/.devcontainer/base.Dockerfile

# [Choice] Debian OS version (use bullseye on local arm64/Apple Silicon): buster, bullseye
ARG VARIANT="bullseye"
FROM nexus.ocr.cr14.net:8003/vscode/devcontainers/rust:0-${VARIANT}

# Non-Interactive installation
ENV DEBIAN_FRONTEND=noninteractive

# [Optional] Uncomment this section to install additional packages.
RUN apt-get update && apt-get -y install --no-install-recommends git git-flow

# Install Rust 1.79.0 specifically
RUN rustup update
RUN rustup install 1.79.0
RUN rustup default 1.79.0

# Add necessary components
RUN rustup component add rust-src clippy --toolchain 1.79.0
