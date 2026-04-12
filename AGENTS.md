# ACES SDL Agent Rules

Use the repo policy tooling before and after implementation work.

## Ground Control Context

This repo's Ground Control project id, workflow commands, and plan
rules live in `.ground-control.yaml` at repo root (with the full
plan rules set under `.gc/plan-rules.md`). Agents read it via the
`gc_get_repo_ground_control_context` MCP tool, which returns the full
workflow config in a single call.

Set `ACES_REQUIREMENT_UID` when the branch name does not already
contain a UID such as `GOV-918`.

The required repo-policy checks and hard rules are enforced by the
`/implement` skill through the plan rules file referenced in
`.ground-control.yaml` — see `.gc/plan-rules.md` for the authoritative
list.
