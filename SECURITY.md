# Security Policy

## Reporting a Vulnerability

Do not report suspected vulnerabilities through public GitHub issues.

Use GitHub private vulnerability reporting for this repository if it is
available. If private reporting is not available, contact the maintainer
privately through the contact path listed on Brad Edwards' GitHub profile and
include `ACES SDL security report` in the subject or first line.

Include enough detail to reproduce and assess the issue:

- affected package, command, schema, or document
- affected version, commit, or branch
- reproduction steps
- expected and actual behavior
- impact
- proof of concept or logs, if available

## Scope

Security reports are most useful for issues in:

- parser and validator behavior
- SDL module resolution and publication
- contract generation and conformance tooling
- CLI behavior
- MCP server behavior
- runtime control-plane code
- repository automation that handles untrusted input

This repository also contains research material and reference ecosystem
material. Reports against archived third-party material may be documented here,
but fixes usually need to happen upstream.

## Response Expectations

ACES SDL is maintained by a sole maintainer. There is no formal security
response SLA. Reports will be reviewed on a best-effort basis, with priority
given to reproducible issues that affect current code, published contracts, or
documented workflows.

Please avoid publishing exploit details until there has been reasonable time to
triage and prepare a fix or mitigation.
