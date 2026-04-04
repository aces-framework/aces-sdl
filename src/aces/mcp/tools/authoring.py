"""SDL authoring tools — validate, scaffold, and instantiate scenarios.

These tools let agents write SDL from scratch, check it for errors,
build up scenarios incrementally, and instantiate parameterized
scenarios with concrete values.
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register SDL authoring tools on the MCP server."""

    @mcp.tool(
        name="sdl_validate",
        description=(
            "Parse and validate SDL YAML content.  Returns either a success "
            "confirmation (with advisories if any) or a structured list of "
            "every error found — parse errors, structural errors, and semantic "
            "validation errors.  All errors are collected before reporting so "
            "you see every issue at once.\n\n"
            "Pass the full YAML scenario text as `sdl_content`.  Optionally "
            "set `structural_only=true` to skip semantic cross-reference "
            "checks (useful for work-in-progress fragments that aren't "
            "complete yet)."
        ),
    )
    def sdl_validate(
        sdl_content: str,
        structural_only: bool = False,
    ) -> str:
        from aces.core.sdl import (
            SDLParseError,
            SDLValidationError,
            parse_sdl,
        )

        try:
            scenario = parse_sdl(
                sdl_content,
                skip_semantic_validation=structural_only,
            )
        except SDLParseError as exc:
            return (
                "PARSE ERROR — the YAML could not be loaded or the "
                "structure does not match the SDL schema.\n\n"
                f"Details:\n{exc.details}"
            )
        except SDLValidationError as exc:
            header = (
                f"VALIDATION ERRORS — {len(exc.errors)} semantic "
                f"issue{'s' if len(exc.errors) != 1 else ''} found.\n\n"
            )
            bullets = "\n".join(f"  - {e}" for e in exc.errors)
            return header + bullets

        # Success path
        parts = [f"VALID — scenario '{scenario.name}' parsed successfully."]

        # Summary
        section_counts = _section_summary(scenario)
        if section_counts:
            parts.append("\nSections populated:")
            for sec, count in section_counts:
                parts.append(f"  {sec}: {count} element{'s' if count != 1 else ''}")

        if scenario.advisories:
            parts.append(f"\nAdvisories ({len(scenario.advisories)}):")
            for adv in scenario.advisories:
                parts.append(f"  - {adv}")

        if structural_only:
            parts.append(
                "\nNote: semantic validation was skipped. Run without "
                "`structural_only` for full cross-reference checking."
            )

        return "\n".join(parts)

    @mcp.tool(
        name="sdl_validate_section",
        description=(
            "Validate a single SDL section fragment by wrapping it in a "
            "minimal scenario context.  Useful when you are building a "
            "scenario piece by piece and want to check one section's syntax "
            "before assembling the whole document.\n\n"
            "Pass the section name (e.g. 'nodes', 'features') and the YAML "
            "content for that section.  Optionally provide `context_yaml` — "
            "additional SDL YAML sections needed to satisfy cross-references "
            "(e.g. nodes referenced by infrastructure).  Structural "
            "validation is always performed; semantic validation runs only "
            "when `context_yaml` is provided."
        ),
    )
    def sdl_validate_section(
        section: str,
        section_yaml: str,
        context_yaml: str = "",
    ) -> str:
        import yaml as _yaml

        from aces.core.sdl import SDLParseError, SDLValidationError, parse_sdl

        section = section.strip().lower().replace("-", "_")
        valid_sections = {
            "nodes", "infrastructure", "features", "conditions",
            "vulnerabilities", "metrics", "evaluations", "tlos", "goals",
            "entities", "injects", "events", "scripts", "stories",
            "content", "accounts", "relationships", "agents", "objectives",
            "workflows", "variables",
        }
        if section not in valid_sections:
            return (
                f"Unknown section '{section}'. "
                f"Valid sections: {', '.join(sorted(valid_sections))}"
            )

        # Build a minimal valid wrapper
        try:
            section_data = _yaml.safe_load(section_yaml)
        except _yaml.YAMLError as exc:
            return f"YAML ERROR in section content:\n{exc}"

        wrapper: dict = {"name": "__mcp_validation_fragment"}
        if context_yaml:
            try:
                ctx = _yaml.safe_load(context_yaml)
                if isinstance(ctx, dict):
                    wrapper.update(ctx)
            except _yaml.YAMLError as exc:
                return f"YAML ERROR in context_yaml:\n{exc}"

        wrapper[section] = section_data
        combined = _yaml.dump(wrapper, default_flow_style=False, sort_keys=False)

        skip_semantic = not bool(context_yaml)
        try:
            parse_sdl(combined, skip_semantic_validation=skip_semantic)
        except SDLParseError as exc:
            return f"PARSE ERROR in '{section}' section:\n{exc.details}"
        except SDLValidationError as exc:
            header = f"VALIDATION ERRORS in '{section}' section ({len(exc.errors)}):\n"
            bullets = "\n".join(f"  - {e}" for e in exc.errors)
            return header + bullets

        mode = "structural" if skip_semantic else "structural + semantic"
        return f"VALID — '{section}' section passes {mode} validation."

    @mcp.tool(
        name="sdl_scaffold",
        description=(
            "Generate a starter SDL scenario skeleton.  Choose a complexity "
            "level: 'minimal' (topology + features only), 'standard' "
            "(adds scoring, entities, accounts), or 'full' (all 21 sections "
            "with placeholder structure).  Optionally provide a scenario name "
            "and description.  The output is valid SDL YAML you can edit."
        ),
    )
    def sdl_scaffold(
        complexity: str = "standard",
        scenario_name: str = "my-scenario",
        description: str = "A new SDL scenario",
    ) -> str:
        key = complexity.lower().strip()
        if key not in ("minimal", "standard", "full"):
            return "Invalid complexity. Choose: 'minimal', 'standard', or 'full'."

        if key == "minimal":
            return _SCAFFOLD_MINIMAL.format(name=scenario_name, desc=description)
        if key == "standard":
            return _SCAFFOLD_STANDARD.format(name=scenario_name, desc=description)
        return _SCAFFOLD_FULL.format(name=scenario_name, desc=description)

    @mcp.tool(
        name="sdl_instantiate",
        description=(
            "Instantiate a parameterized SDL scenario by substituting "
            "concrete values for ${var} placeholders.  Pass the SDL YAML and "
            "a JSON-formatted dictionary of parameter values.  Returns the "
            "fully resolved scenario summary or detailed errors if "
            "instantiation fails."
        ),
    )
    def sdl_instantiate(
        sdl_content: str,
        parameters_json: str = "{}",
    ) -> str:
        import json

        from aces.core.sdl import (
            SDLInstantiationError,
            SDLParseError,
            SDLValidationError,
            instantiate_scenario,
            parse_sdl,
        )

        try:
            params = json.loads(parameters_json)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON in parameters_json: {exc}"
        if not isinstance(params, dict):
            return "parameters_json must be a JSON object (dictionary)."

        try:
            scenario = parse_sdl(sdl_content)
        except SDLParseError as exc:
            return f"PARSE ERROR:\n{exc.details}"
        except SDLValidationError as exc:
            bullets = "\n".join(f"  - {e}" for e in exc.errors)
            return f"VALIDATION ERRORS:\n{bullets}"

        try:
            concrete = instantiate_scenario(scenario, parameters=params)
        except SDLInstantiationError as exc:
            bullets = "\n".join(f"  - {e}" for e in exc.errors)
            return f"INSTANTIATION ERRORS ({len(exc.errors)}):\n{bullets}"

        parts = [
            f"INSTANTIATED — scenario '{concrete.name}' fully resolved.",
            f"Parameters used: {concrete.instantiation_parameters}",
        ]
        section_counts = _section_summary(concrete)
        if section_counts:
            parts.append("\nSections:")
            for sec, count in section_counts:
                parts.append(f"  {sec}: {count}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECTION_FIELDS = [
    "nodes", "infrastructure", "features", "conditions", "vulnerabilities",
    "metrics", "evaluations", "tlos", "goals", "entities", "injects",
    "events", "scripts", "stories", "content", "accounts", "relationships",
    "agents", "objectives", "workflows", "variables",
]


def _section_summary(scenario: object) -> list[tuple[str, int]]:
    """Return (section_name, element_count) for non-empty sections."""
    counts: list[tuple[str, int]] = []
    for field in _SECTION_FIELDS:
        data = getattr(scenario, field, None)
        if data:
            counts.append((field, len(data)))
    return counts


# ---------------------------------------------------------------------------
# Scaffold templates
# ---------------------------------------------------------------------------

_SCAFFOLD_MINIMAL = """\
name: {name}
description: {desc}

nodes:
  net-switch:
    type: Switch
    description: Main network

  server-01:
    type: VM
    os: linux
    resources: {{ram: 2 GiB, cpu: 1}}
    features: [my-service]
    services:
      - {{port: 443, name: https}}

infrastructure:
  net-switch:
    count: 1
    properties: {{cidr: 10.0.0.0/24, gateway: 10.0.0.1}}
  server-01:
    count: 1
    links: [net-switch]

features:
  my-service: {{type: Service, source: my-package}}
"""

_SCAFFOLD_STANDARD = """\
name: {name}
description: {desc}

nodes:
  corp-net:
    type: Switch
    description: Corporate network

  web-server:
    type: VM
    os: linux
    resources: {{ram: 4 GiB, cpu: 2}}
    features: {{web-app: web-admin}}
    conditions: {{web-healthy: web-admin}}
    services:
      - {{port: 443, name: https}}
    roles:
      web-admin: www-data

  db-server:
    type: VM
    os: linux
    resources: {{ram: 4 GiB, cpu: 2}}
    features: {{database: dba}}
    services:
      - {{port: 5432, name: postgres}}
    roles:
      dba: postgres

infrastructure:
  corp-net:
    count: 1
    properties: {{cidr: 10.0.0.0/24, gateway: 10.0.0.1}}
  web-server:
    count: 1
    links: [corp-net]
  db-server:
    count: 1
    links: [corp-net]

features:
  web-app: {{type: Service, source: my-webapp}}
  database: {{type: Service, source: postgresql-16}}

conditions:
  web-healthy:
    command: "curl -sf https://localhost/ || exit 1"
    interval: 15

vulnerabilities:
  sqli:
    name: SQL Injection
    description: SQL injection in login form
    technical: true
    class: CWE-89

metrics:
  web-uptime:
    type: CONDITIONAL
    max-score: 100
    condition: web-healthy

evaluations:
  availability:
    metrics: [web-uptime]
    min-score: 75

tlos:
  defend-web:
    name: Defend the web application
    evaluation: availability

goals:
  exercise-goal:
    tlos: [defend-web]

entities:
  blue-team:
    name: Blue Team
    role: Blue
    tlos: [defend-web]
  red-team:
    name: Red Team
    role: Red

accounts:
  web-admin-account:
    username: webadmin
    node: web-server
    password_strength: strong
  db-admin-account:
    username: dbadmin
    node: db-server
    password_strength: medium

relationships:
  web-to-db:
    type: connects_to
    source: web-app
    target: database
    properties: {{protocol: tcp, port: "5432"}}
"""

_SCAFFOLD_FULL = """\
name: {name}
description: {desc}

# --- Parameterization ---
variables:
  exercise_speed:
    type: number
    default: 1.0
    description: Story playback speed multiplier
  admin_password_strength:
    type: string
    default: strong
    allowed_values: [weak, medium, strong]

# --- Topology ---
nodes:
  corp-net:
    type: Switch
    description: Corporate network

  web-server:
    type: VM
    os: linux
    resources: {{ram: 4 GiB, cpu: 2}}
    features: {{web-app: web-admin}}
    conditions: {{web-healthy: web-admin}}
    vulnerabilities: [sqli]
    services:
      - {{port: 443, name: https}}
    roles:
      web-admin:
        username: www-data
        entities: [blue-team.web-ops]

  db-server:
    type: VM
    os: linux
    resources: {{ram: 4 GiB, cpu: 2}}
    features: {{database: dba}}
    services:
      - {{port: 5432, name: postgres}}
    roles:
      dba: postgres
    asset_value:
      confidentiality: high
      integrity: high

infrastructure:
  corp-net:
    count: 1
    properties: {{cidr: 10.0.0.0/24, gateway: 10.0.0.1}}
  web-server:
    count: 1
    links: [corp-net]
  db-server:
    count: 1
    links: [corp-net]

# --- Software ---
features:
  web-app: {{type: Service, source: my-webapp}}
  database: {{type: Service, source: postgresql-16}}

conditions:
  web-healthy:
    command: "curl -sf https://localhost/ || exit 1"
    interval: 15

vulnerabilities:
  sqli:
    name: SQL Injection
    description: SQL injection in application
    technical: true
    class: CWE-89

# --- Scoring Pipeline ---
metrics:
  web-uptime:
    type: CONDITIONAL
    max-score: 100
    condition: web-healthy
  report-quality:
    type: MANUAL
    max-score: 50

evaluations:
  overall:
    metrics: [web-uptime, report-quality]
    min-score: 75

tlos:
  defend-web:
    name: Defend the web application
    evaluation: overall

goals:
  exercise-goal:
    tlos: [defend-web]

# --- Teams ---
entities:
  blue-team:
    name: Blue Team
    role: Blue
    tlos: [defend-web]
    entities:
      web-ops: {{name: Web Operations}}
  red-team:
    name: Red Team
    role: Red

# --- Orchestration ---
injects:
  attack-brief:
    source: attack-briefing-doc
    from_entity: red-team
    to_entities: [blue-team]

events:
  attack-start:
    injects: [attack-brief]

scripts:
  main-timeline:
    start-time: 0
    end-time: 4 hour
    speed: ${{exercise_speed}}
    events:
      attack-start: 30 min

stories:
  exercise:
    speed: ${{exercise_speed}}
    scripts: [main-timeline]

# --- Content ---
content:
  seed-data:
    type: dataset
    target: db-server
    format: sql
    source: seed-data-pkg

# --- Accounts ---
accounts:
  web-admin-account:
    username: webadmin
    node: web-server
    password_strength: ${{admin_password_strength}}
  db-admin-account:
    username: dbadmin
    node: db-server
    password_strength: medium

# --- Relationships ---
relationships:
  web-to-db:
    type: connects_to
    source: web-app
    target: database
    properties: {{protocol: tcp, port: "5432"}}

# --- Agents ---
agents:
  red-agent:
    entity: red-team
    actions: [Scan, Exploit]
    initial_knowledge:
      hosts: [web-server]
      subnets: [corp-net]
      services: [https]

# --- Objectives ---
objectives:
  red-access:
    agent: red-agent
    actions: [Scan, Exploit]
    targets: [web-server, sqli]
    success:
      conditions: [web-healthy]
    window:
      stories: [exercise]
  blue-defend:
    entity: blue-team
    success:
      goals: [exercise-goal]
    depends_on: [red-access]

# --- Workflows ---
workflows:
  exercise-flow:
    start: run-attack
    steps:
      run-attack:
        type: objective
        objective: red-access
        on-success: run-defense
      run-defense:
        type: objective
        objective: blue-defend
        on-success: done
      done:
        type: end
"""
