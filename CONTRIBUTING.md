# Contributing to ACES SDL

ACES SDL is a research-oriented engineering project. Contributions are useful
when they make the language, reference implementation, contracts, examples, or
documentation more precise and easier to validate.

## Before Opening a Pull Request

- For small documentation fixes, typo fixes, and narrow test improvements, a
  pull request is enough.
- For SDL language changes, contract changes, processor behavior changes, or
  backend conformance changes, open an issue first. Those changes can affect
  authored scenario meaning and generated artifacts.
- Keep unrelated changes in separate pull requests.
- Base pull requests on `dev`, not `main`. `main` is the stable release line;
  `dev` is the integration branch.

## Development Setup

Prerequisites:

- Python 3.11 or newer
- [uv](https://github.com/astral-sh/uv)
- [nox](https://nox.thea.codes/) or `uvx nox`

Set up the Python implementation:

```shell
git clone https://github.com/autarchy-ai/aces.git
cd aces/implementations/python
uv sync --all-extras
```

## Making Changes

1. Fork the repository and create a branch from `dev`.
2. Make the smallest coherent change that solves the issue.
3. Add or update tests when behavior changes.
4. Update examples, schemas, contracts, or documentation when the public
   surface changes.
5. Add a towncrier fragment under [`changelog.d/`](changelog.d/) unless the
   change is only internal maintenance. See
   [`changelog.d/README.md`](changelog.d/README.md).
6. Run the relevant checks locally.
7. Open a pull request against `dev` with a concrete description of what
   changed and why.

## Verification

The full repository gate is:

```shell
uvx nox -s verify
```

Useful narrower sessions:

```shell
uvx nox -s tests
uvx nox -s docs
uvx nox -l
```

Run the full gate before requesting review for language, contract, generated
artifact, or shared runtime changes.

## Changelog

Release notes are generated from towncrier fragments under `changelog.d/`.
Do not hand-edit `CHANGELOG.md`.

Fragment names follow the pattern described in
[`changelog.d/README.md`](changelog.d/README.md).

## Security Reports

Do not open public issues for suspected security vulnerabilities. See
[SECURITY.md](SECURITY.md).

## Community Expectations

Participation in this project is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
