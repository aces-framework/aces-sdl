# aces-sdl

A standalone cyber range scenario description language and runtime ecosystem.

`aces-sdl` is a fully working SDL stack for describing cyber range scenarios
and experiments, validating their meaning, compiling runtime models, and
defining portable backend contracts.

It is designed to stand on its own as a coherent system. It also serves as a
working, contrastive ecosystem for RFC and standards work by the Red Queen
Working Group, so language, semantics, runtime, and assurance questions can be
tested in a live codebase rather than only in abstract design discussions.

This repository includes:

- author-facing SDL models and parsing
- semantic validation and formal semantic artifacts
- runtime compilation, planning, and control-plane contracts
- schemas and backend conformance fixtures
- SDL/runtime-focused CLI commands, docs, examples, and tests

This repository is not a standards document. It is an independent,
backend-agnostic implementation that can inform, challenge, and sharpen future
standards work in this area.

The Python package namespace is `aces.*`, and the CLI entrypoint is `aces`.
