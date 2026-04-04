"""SDL reference and learning tools.

These tools teach agents about the SDL from scratch — no prior knowledge
required.  They expose the language overview, per-section documentation,
and annotated real-world examples.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Docs / examples on disk — allowlisted filenames only
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[4]  # src/aces/mcp/tools -> repo root
_DOCS_DIR = _REPO_ROOT / "docs" / "sdl"
_EXAMPLES_DIR = _REPO_ROOT / "examples"

_ALLOWED_DOCS = frozenset({"sections.md", "parser.md", "validation.md"})
_ALLOWED_EXAMPLES = frozenset({
    "hospital-ransomware-surgery-day.sdl.yaml",
    "satcom-release-poisoning.sdl.yaml",
    "port-authority-surge-response.sdl.yaml",
})


def _read_doc(name: str) -> str:
    if name not in _ALLOWED_DOCS:
        return f"Documentation file not available: {name}"
    path = _DOCS_DIR / name
    if not path.exists():
        return f"Documentation file not found: {name}"
    return path.read_text()


def _read_example(name: str) -> str:
    if name not in _ALLOWED_EXAMPLES:
        return f"Example file not available: {name}"
    path = _EXAMPLES_DIR / name
    if not path.exists():
        return f"Example file not found: {name}"
    return path.read_text()


# ---------------------------------------------------------------------------
# Section-level reference snippets
# ---------------------------------------------------------------------------

# Maps each section name to the heading anchor used in sections.md so we
# can extract just the relevant portion.
_SECTION_NAMES: dict[str, str] = {
    "nodes": "Nodes",
    "infrastructure": "Infrastructure",
    "features": "Features",
    "conditions": "Conditions",
    "vulnerabilities": "Vulnerabilities",
    "metrics": "Scoring Pipeline: Metrics, Evaluations, TLOs, Goals",
    "evaluations": "Scoring Pipeline: Metrics, Evaluations, TLOs, Goals",
    "tlos": "Scoring Pipeline: Metrics, Evaluations, TLOs, Goals",
    "goals": "Scoring Pipeline: Metrics, Evaluations, TLOs, Goals",
    "scoring": "Scoring Pipeline: Metrics, Evaluations, TLOs, Goals",
    "entities": "Entities",
    "injects": "Orchestration: Injects, Events, Scripts, Stories",
    "events": "Orchestration: Injects, Events, Scripts, Stories",
    "scripts": "Orchestration: Injects, Events, Scripts, Stories",
    "stories": "Orchestration: Injects, Events, Scripts, Stories",
    "orchestration": "Orchestration: Injects, Events, Scripts, Stories",
    "content": "Content",
    "accounts": "Accounts",
    "relationships": "Relationships",
    "agents": "Agents",
    "objectives": "Objectives",
    "workflows": "Workflows",
    "variables": "Variables",
}


def _extract_section(doc_text: str, heading: str) -> str:
    """Extract a single ## section from the sections.md document."""
    marker = f"## {heading}\n"
    start = doc_text.find(marker)
    if start == -1:
        return f"Section '{heading}' not found in reference docs."
    # Find end: next ## heading or end of file
    next_h2 = doc_text.find("\n## ", start + len(marker))
    if next_h2 == -1:
        return doc_text[start:]
    return doc_text[start:next_h2].rstrip()


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------


def register(mcp: FastMCP) -> None:
    """Register SDL reference/learning tools on the MCP server."""

    @mcp.tool(
        name="sdl_overview",
        description=(
            "Get a comprehensive overview of the ACES Scenario Description "
            "Language (SDL). Returns what the SDL is, its 21 sections, how "
            "parsing/validation works, the variable system, and a complete "
            "minimal example. Start here if you have never seen the SDL before."
        ),
    )
    def sdl_overview() -> str:
        return _OVERVIEW_TEXT

    @mcp.tool(
        name="sdl_section_reference",
        description=(
            "Get detailed documentation for a specific SDL section including "
            "its schema, fields, YAML examples, shorthands, and validation "
            "rules.  Valid section names: nodes, infrastructure, features, "
            "conditions, vulnerabilities, scoring (metrics+evaluations+tlos+"
            "goals), entities, orchestration (injects+events+scripts+stories), "
            "content, accounts, relationships, agents, objectives, workflows, "
            "variables.  You can also pass the individual section name like "
            "'metrics' or 'events'."
        ),
    )
    def sdl_section_reference(section: str) -> str:
        key = section.lower().strip()
        if key not in _SECTION_NAMES:
            valid = sorted(set(_SECTION_NAMES.keys()))
            return (
                f"Unknown section '{section}'. "
                f"Valid names: {', '.join(valid)}"
            )
        heading = _SECTION_NAMES[key]
        doc_text = _read_doc("sections.md")
        extracted = _extract_section(doc_text, heading)

        # Append relevant validation rules
        validation_text = _read_doc("validation.md")
        verify_tag = f"verify_{key}"
        # Try to find the matching validation pass description
        val_lines: list[str] = []
        for line in validation_text.splitlines():
            if verify_tag in line.lower().replace("-", "_"):
                val_lines.append(line)
        if val_lines:
            extracted += "\n\n### Validation Rules\n\n" + "\n".join(val_lines)

        return extracted

    @mcp.tool(
        name="sdl_get_example",
        description=(
            "Get a complete, real-world annotated SDL scenario example. "
            "Available examples: 'hospital' (hospital ransomware exercise, "
            "~750 lines, uses all 21 sections), 'satcom' (satellite supply-chain "
            "exercise, ~750 lines), 'port' (port authority OT exercise, ~680 lines), "
            "'minimal' (a small annotated pentest-lab example to learn the basics). "
            "Use 'hospital' for a comprehensive reference of all SDL features."
        ),
    )
    def sdl_get_example(
        name: str,
    ) -> str:
        key = name.lower().strip()
        if key in ("hospital", "hospital-ransomware", "ransomware"):
            return _read_example("hospital-ransomware-surgery-day.sdl.yaml")
        if key in ("satcom", "satellite", "supply-chain", "release-poisoning"):
            return _read_example("satcom-release-poisoning.sdl.yaml")
        if key in ("port", "port-authority", "ot", "surge"):
            return _read_example("port-authority-surge-response.sdl.yaml")
        if key in ("minimal", "simple", "small", "pentest", "lab"):
            return _MINIMAL_EXAMPLE
        return (
            f"Unknown example '{name}'. "
            "Available: 'hospital', 'satcom', 'port', 'minimal'"
        )

    @mcp.tool(
        name="sdl_parser_reference",
        description=(
            "Get documentation about SDL parser behavior: key normalization "
            "(case-insensitive fields), shorthand expansion rules, the variable "
            "system (${var} syntax), OCR duration grammar (e.g. '1h 30min'), "
            "and the parse/validate pipeline stages."
        ),
    )
    def sdl_parser_reference() -> str:
        return _read_doc("parser.md")

    @mcp.tool(
        name="sdl_validation_reference",
        description=(
            "Get documentation about SDL semantic validation: all 22 named "
            "validation passes, cross-reference resolution rules, error "
            "reporting, advisories, and how ambiguous references are handled."
        ),
    )
    def sdl_validation_reference() -> str:
        return _read_doc("validation.md")


# ---------------------------------------------------------------------------
# Static content
# ---------------------------------------------------------------------------

_MINIMAL_EXAMPLE = """\
# Minimal SDL Example: Pentest Lab
# This demonstrates the core SDL structure with a small, self-contained scenario.

name: simple-pentest-lab
description: Web app with SQL injection targeting a database

# --- Topology: nodes define VMs and network switches ---
nodes:
  lab-net:
    type: Switch                         # pure connectivity, no OS/resources
    description: Lab network

  webapp:
    type: VM
    os: linux
    resources: {ram: 2 GiB, cpu: 1}      # human-readable RAM
    features: [flask-app]                 # list shorthand for feature bindings
    services:
      - {port: 8080, name: http}          # exposed network service
    vulnerabilities: [sqli]

  database:
    type: VM
    os: linux
    resources: {ram: 1 GiB, cpu: 1}
    features: [postgres]
    services:
      - {port: 5432, name: postgresql}
    asset_value:
      confidentiality: high               # CIA triad classification

# --- Deployment: how many of each, which networks, IPs ---
infrastructure:
  lab-net:
    count: 1
    properties: {cidr: 10.0.0.0/24, gateway: 10.0.0.1}
  webapp:
    count: 1
    links: [lab-net]                       # connected to lab-net switch
  database:
    count: 1
    links: [lab-net]

# --- Software deployed onto VMs ---
features:
  flask-app: {type: Service, source: vulnerable-flask-app}
  postgres: {type: Service, source: postgresql-16}

# --- Security weaknesses ---
vulnerabilities:
  sqli:
    name: SQL Injection
    description: SQLi in login form allows auth bypass
    technical: true
    class: CWE-89                          # must be CWE-\\d+ format

# --- Typed edges between elements ---
relationships:
  app-to-db:
    type: connects_to                      # authenticates_with, trusts, federates_with,
    source: flask-app                      #   connects_to, depends_on, manages, replicates_to
    target: postgres
    properties: {protocol: tcp, port: "5432"}

# --- User accounts ---
accounts:
  db-admin:
    username: admin
    node: database                         # must reference a VM node
    password_strength: weak                # weak, medium, strong, none

# --- Health checks ---
conditions:
  web-alive:
    command: "curl -sf http://localhost:8080/ || exit 1"
    interval: 15

# --- Scoring pipeline: conditions -> metrics -> evaluations -> TLOs -> goals ---
metrics:
  uptime:
    type: CONDITIONAL
    max-score: 100
    condition: web-alive

evaluations:
  basic-eval:
    metrics: [uptime]
    min-score: 75                          # shorthand for {percentage: 75}

tlos:
  web-defense:
    name: Defend the web application
    evaluation: basic-eval

goals:
  pass:
    tlos: [web-defense]

# --- Teams / people ---
entities:
  blue-team:
    name: Blue Team
    role: Blue                             # Blue, Red, White, Green
    tlos: [web-defense]
  red-team:
    name: Red Team
    role: Red

# --- Parameterization (${var} syntax, resolved at instantiation, not parse time) ---
variables:
  lab_cidr:
    type: string
    default: "10.0.0.0/24"
    description: Lab network CIDR block
"""

_OVERVIEW_TEXT = """\
# ACES Scenario Description Language (SDL) Overview

## What is the SDL?

The ACES SDL is a **YAML-based, backend-agnostic specification language** for \
describing cyber range scenarios and experiments. It defines *what a scenario \
means* — not how to deploy it. Backend implementations realize SDL \
specifications through runtime contracts.

It descends from the Open Cyber Range (OCR) SDL and extends it with 7 \
additional sections for richer experiment semantics.

## The 21 Sections

A scenario is a YAML document with a required `name` and up to 21 optional \
sections, organized into four concerns:

### Topology & Software (5 sections)
| Section | Purpose |
|---------|---------|
| `nodes` | VMs and network switches — the compute/network topology |
| `infrastructure` | Deployment: counts, links, dependencies, IPs, CIDRs, ACLs |
| `features` | Software (Service/Configuration/Artifact) deployed to VMs |
| `conditions` | Health checks (command+interval or library source) |
| `vulnerabilities` | CWE-classified weaknesses |

### Scoring Pipeline (4 sections)
| Section | Purpose |
|---------|---------|
| `metrics` | Scoring criteria: CONDITIONAL (automated) or MANUAL |
| `evaluations` | Metric groups with pass/fail thresholds |
| `tlos` | Training Learning Objectives linked to evaluations |
| `goals` | High-level goals composed of TLOs |

Flow: `conditions -> metrics -> evaluations -> TLOs -> goals`

### Exercise Orchestration (4 sections)
| Section | Purpose |
|---------|---------|
| `entities` | Teams, organizations, people (recursive hierarchy) |
| `injects` | Actions between entities |
| `events` | Triggered actions combining conditions + injects |
| `scripts` | Timed event sequences with human-readable durations |
| `stories` | Top-level orchestration grouping scripts |

### Extended Experiment Semantics (7 sections)
| Section | Purpose |
|---------|---------|
| `content` | Data placed into systems (files, datasets, emails) |
| `accounts` | User accounts on nodes |
| `relationships` | Typed directed edges (auth, trust, federation, etc.) |
| `agents` | Autonomous participants with actions/knowledge/scope |
| `objectives` | Declarative tasks: actor + targets + success + window |
| `workflows` | Branching/parallel control graphs over objectives |
| `variables` | Parameterization via `${var_name}` syntax |

### Top-level Composition Fields
- `name` (required), `version`, `description`
- `module` — publishable module descriptor
- `imports` — module imports (`local:`, `oci:`, `locked:`)

## Key Concepts

### Variables
- `${var_name}` placeholders in field values (NOT in mapping keys)
- Preserved as literal strings during parsing; resolved at instantiation
- Types: string, integer, boolean, number
- Can have defaults, allowed_values, required flag

### Shorthand Expansion
The parser auto-expands common patterns:
- `source: "pkg"` → `{name: "pkg", version: "*"}`
- `infrastructure: {node: 3}` → `{node: {count: 3}}`
- `roles: {admin: "user"}` → `{admin: {username: "user"}}`
- `min-score: 50` → `{percentage: 50}`
- `features: [nginx, php]` → `{nginx: "", php: ""}`

### Key Normalization
- Field keys are case-insensitive: `Name` → `name`, `Min-Score` → `min_score`
- User-defined names (node names, feature names, etc.) are preserved as-is

### Cross-Reference System
- Named elements can be referenced by bare name when unambiguous: `webapp`
- Qualified refs when disambiguation needed: `nodes.webapp`, `features.nginx`
- Nested entities use dot-notation: `blue-team.alice`
- Named services: `nodes.<node>.services.<service_name>`
- Named ACLs: `infrastructure.<infra>.acls.<acl_name>`

### Validation Pipeline
1. YAML parsing (`yaml.safe_load()`)
2. Key normalization
3. Shorthand expansion
4. Pydantic structural validation
5. 22-pass semantic validation (cross-references, cycles, IP/CIDR, etc.)
All errors collected before reporting — authors see every issue at once.

### Duration Grammar
Script/event times accept: `1h 30min`, `2 days`, `1m+30`, `500ms`
Units: y, mon, w, d, h, m/min, s/sec, ms, us, ns

## Quick Example

```yaml
name: simple-lab
description: Basic web app scenario

nodes:
  net: {type: Switch}
  web: {type: VM, os: linux, resources: {ram: 2 GiB, cpu: 1}, features: [app]}
  db:  {type: VM, os: linux, resources: {ram: 1 GiB, cpu: 1}, features: [postgres]}

infrastructure:
  net: {count: 1, properties: {cidr: 10.0.0.0/24}}
  web: {count: 1, links: [net]}
  db:  {count: 1, links: [net]}

features:
  app:      {type: Service, source: flask-app}
  postgres: {type: Service, source: postgresql-16}

vulnerabilities:
  sqli: {name: SQL Injection, technical: true, class: CWE-89}

relationships:
  app-to-db: {type: connects_to, source: app, target: postgres}
```

## Python API

```python
from aces.core.sdl import parse_sdl, parse_sdl_file, instantiate_scenario

# Parse from string or file
scenario = parse_sdl(yaml_string)
scenario = parse_sdl_file(Path("scenario.yaml"))

# Structural only (skip cross-reference checks)
scenario = parse_sdl(yaml_string, skip_semantic_validation=True)

# Instantiate with concrete variable values
concrete = instantiate_scenario(scenario, parameters={"domain": "corp.local"})

# Check non-fatal advisories
for advisory in scenario.advisories:
    print(advisory)
```

## Error Types
- `SDLParseError` — YAML syntax or structural issues
- `SDLValidationError` — semantic issues (has `.errors` list with ALL issues)
- `SDLInstantiationError` — variable binding failures

Use `sdl_section_reference` to learn about any specific section in detail.
Use `sdl_get_example` to see complete real-world scenarios.
Use `sdl_validate` to check your SDL YAML.
"""
