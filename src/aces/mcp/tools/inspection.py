"""SDL inspection tools — analyze, query, and summarize parsed scenarios.

These tools work on SDL YAML that has already been written.  They let
agents understand the structure of a scenario, look up individual
elements, trace cross-references, and get high-level summaries.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register SDL inspection/query tools on the MCP server."""

    @mcp.tool(
        name="sdl_summarize",
        description=(
            "Parse an SDL YAML scenario and return a structured summary: "
            "scenario name/description, which sections are populated, element "
            "counts, variables defined, entities hierarchy, and high-level "
            "topology stats (VM count, switch count, network links).  "
            "Useful for getting a quick understanding of an existing scenario."
        ),
    )
    def sdl_summarize(sdl_content: str) -> str:
        scenario = _parse_or_error(sdl_content)
        if isinstance(scenario, str):
            return scenario
        return _build_summary(scenario)

    @mcp.tool(
        name="sdl_list_elements",
        description=(
            "List all named elements in a parsed SDL scenario, optionally "
            "filtered by section.  Returns element names grouped by section.  "
            "Pass `section` to filter (e.g. 'nodes', 'accounts').  "
            "Pass `section='all'` or omit it to list everything."
        ),
    )
    def sdl_list_elements(
        sdl_content: str,
        section: str = "all",
    ) -> str:
        scenario = _parse_or_error(sdl_content)
        if isinstance(scenario, str):
            return scenario
        return _list_elements(scenario, section.lower().strip())

    @mcp.tool(
        name="sdl_get_element",
        description=(
            "Get detailed information about a specific named element in a "
            "scenario.  Use a bare name like 'web-server' or a qualified "
            "ref like 'nodes.web-server'.  Returns all fields, references "
            "to/from this element, and related context."
        ),
    )
    def sdl_get_element(
        sdl_content: str,
        element_name: str,
    ) -> str:
        scenario = _parse_or_error(sdl_content)
        if isinstance(scenario, str):
            return scenario
        return _get_element_detail(scenario, element_name.strip())

    @mcp.tool(
        name="sdl_check_references",
        description=(
            "Analyze cross-references in a scenario.  For a given element "
            "name, shows what it references (outgoing) and what references "
            "it (incoming).  Helps understand dependency chains and "
            "connectivity.  If no element_name is given, returns a full "
            "reference graph summary."
        ),
    )
    def sdl_check_references(
        sdl_content: str,
        element_name: str = "",
    ) -> str:
        scenario = _parse_or_error(sdl_content)
        if isinstance(scenario, str):
            return scenario
        if element_name.strip():
            return _element_references(scenario, element_name.strip())
        return _full_reference_graph(scenario)

    @mcp.tool(
        name="sdl_diagram",
        description=(
            "Generate an ASCII topology diagram of the scenario's network "
            "layout showing switches, VMs connected to each switch, and "
            "inter-node dependencies.  Useful for visualizing the scenario "
            "structure."
        ),
    )
    def sdl_diagram(sdl_content: str) -> str:
        scenario = _parse_or_error(sdl_content)
        if isinstance(scenario, str):
            return scenario
        return _build_diagram(scenario)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SECTION_FIELDS = [
    "nodes", "infrastructure", "features", "conditions", "vulnerabilities",
    "metrics", "evaluations", "tlos", "goals", "entities", "injects",
    "events", "scripts", "stories", "content", "accounts", "relationships",
    "agents", "objectives", "workflows", "variables",
]


def _parse_or_error(sdl_content: str):
    """Attempt to parse SDL, returning a Scenario or an error string."""
    from aces.core.sdl import SDLParseError, SDLValidationError, parse_sdl

    try:
        return parse_sdl(sdl_content, skip_semantic_validation=True)
    except SDLParseError as exc:
        return f"PARSE ERROR:\n{exc.details}"
    except SDLValidationError as exc:
        # Shouldn't happen with skip_semantic_validation=True, but be safe
        bullets = "\n".join(f"  - {e}" for e in exc.errors)
        return f"VALIDATION ERRORS:\n{bullets}"


def _build_summary(scenario) -> str:
    """Build a human-readable summary of a scenario."""
    from aces.core.sdl.entities import flatten_entities
    from aces.core.sdl.nodes import NodeType

    lines = [
        f"Scenario: {scenario.name}",
    ]
    if scenario.description:
        lines.append(f"Description: {scenario.description.strip()}")
    if scenario.version != "*":
        lines.append(f"Version: {scenario.version}")

    # Section counts
    lines.append("\n--- Sections ---")
    total_elements = 0
    for field in _SECTION_FIELDS:
        data = getattr(scenario, field, None)
        if data:
            count = len(data)
            total_elements += count
            lines.append(f"  {field}: {count}")
    lines.append(f"  (total named elements: {total_elements})")

    # Topology stats
    vm_count = 0
    switch_count = 0
    for node in scenario.nodes.values():
        if node.type == NodeType.VM:
            vm_count += 1
        elif node.type == NodeType.SWITCH:
            switch_count += 1
    if scenario.nodes:
        lines.append(f"\n--- Topology ---")
        lines.append(f"  VMs: {vm_count}")
        lines.append(f"  Switches: {switch_count}")

    # Variables
    if scenario.variables:
        lines.append(f"\n--- Variables ---")
        for var_name, var in scenario.variables.items():
            default_str = f" (default: {var.default})" if var.default is not None else ""
            req = " [required]" if var.required else ""
            lines.append(f"  ${{{var_name}}}: {var.type.value}{default_str}{req}")

    # Entities hierarchy
    if scenario.entities:
        lines.append(f"\n--- Entities ---")
        _format_entities(scenario.entities, lines, indent=2)

    # Objectives summary
    if scenario.objectives:
        lines.append(f"\n--- Objectives ---")
        for obj_name, obj in scenario.objectives.items():
            actor = obj.agent or obj.entity
            deps = f" (depends: {', '.join(obj.depends_on)})" if obj.depends_on else ""
            lines.append(f"  {obj_name}: actor={actor}{deps}")

    # Workflows summary
    if scenario.workflows:
        lines.append(f"\n--- Workflows ---")
        for wf_name, wf in scenario.workflows.items():
            step_count = len(wf.steps) if wf.steps else 0
            lines.append(f"  {wf_name}: {step_count} steps, start={wf.start}")

    return "\n".join(lines)


def _format_entities(entities: dict, lines: list[str], indent: int) -> None:
    """Recursively format entity hierarchy."""
    prefix = " " * indent
    for name, entity in entities.items():
        role_str = f" ({entity.role.value})" if entity.role and hasattr(entity.role, 'value') else ""
        display = entity.name or name
        lines.append(f"{prefix}{name}: {display}{role_str}")
        if entity.entities:
            _format_entities(entity.entities, lines, indent + 2)


def _list_elements(scenario, section_filter: str) -> str:
    """List named elements, optionally filtered by section."""
    from aces.core.sdl.entities import flatten_entities

    lines: list[str] = []
    for field in _SECTION_FIELDS:
        if section_filter not in ("all", "") and field != section_filter:
            continue
        data = getattr(scenario, field, None)
        if not data:
            continue
        lines.append(f"\n{field}:")
        for name in data:
            lines.append(f"  - {name}")
        # Special: show nested entities
        if field == "entities":
            flat = flatten_entities(data)
            nested = [n for n in flat if "." in n]
            if nested:
                lines.append("  (nested entities):")
                for n in nested:
                    lines.append(f"    - {n}")

    if not lines:
        if section_filter not in ("all", ""):
            return f"Section '{section_filter}' is empty or does not exist."
        return "Scenario has no named elements."

    return "\n".join(lines)


def _get_element_detail(scenario, name: str) -> str:
    """Get detailed info about a named element."""
    # Try qualified ref first (e.g. "nodes.web-server")
    if "." in name:
        parts = name.split(".", 1)
        section_name, element_name = parts[0], parts[1]
        data = getattr(scenario, section_name, None)
        if isinstance(data, dict) and element_name in data:
            return _format_element(section_name, element_name, data[element_name])

    # Search all sections for bare name
    matches: list[tuple[str, str, object]] = []
    for field in _SECTION_FIELDS:
        data = getattr(scenario, field, None)
        if not data:
            continue
        if name in data:
            matches.append((field, name, data[name]))

    if not matches:
        # Try nested entity names
        from aces.core.sdl.entities import flatten_entities
        if scenario.entities:
            flat = flatten_entities(scenario.entities)
            if name in flat:
                return _format_element("entities", name, flat[name])

        return (
            f"Element '{name}' not found. "
            "Use `sdl_list_elements` to see all available elements, "
            "or try a qualified ref like 'nodes.my-node'."
        )

    if len(matches) == 1:
        section, ename, obj = matches[0]
        return _format_element(section, ename, obj)

    # Ambiguous
    lines = [f"Ambiguous name '{name}' found in multiple sections:"]
    for section, ename, _ in matches:
        lines.append(f"  - {section}.{ename}")
    lines.append("Use a qualified ref to disambiguate.")
    return "\n".join(lines)


def _format_element(section: str, name: str, obj: object) -> str:
    """Format a single element's details as readable text."""
    lines = [f"{section}.{name}"]

    if hasattr(obj, "model_dump"):
        data = obj.model_dump(exclude_defaults=True, exclude_none=True)
        for key, value in data.items():
            if isinstance(value, dict) and not value:
                continue
            if isinstance(value, list) and not value:
                continue
            lines.append(f"  {key}: {_format_value(value)}")
    else:
        lines.append(f"  {obj!r}")

    return "\n".join(lines)


def _format_value(value: object, indent: int = 4) -> str:
    """Format a value for display, handling nested structures."""
    if isinstance(value, dict):
        if not value:
            return "{}"
        parts = []
        prefix = " " * indent
        for k, v in value.items():
            parts.append(f"{prefix}{k}: {_format_value(v, indent + 2)}")
        return "\n" + "\n".join(parts)
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(isinstance(v, str) for v in value):
            return f"[{', '.join(str(v) for v in value)}]"
        parts = []
        prefix = " " * indent
        for v in value:
            parts.append(f"{prefix}- {_format_value(v, indent + 2)}")
        return "\n" + "\n".join(parts)
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _element_references(scenario, name: str) -> str:
    """Show what an element references and what references it."""
    outgoing: list[str] = []
    incoming: list[str] = []

    ref_map = _build_reference_map(scenario)
    for (src_section, src_name), targets in ref_map.items():
        src_key = f"{src_section}.{src_name}"
        for tgt in targets:
            if src_name == name or src_key == name:
                outgoing.append(tgt)
            if tgt == name or tgt.endswith(f".{name}"):
                incoming.append(src_key)

    lines = [f"References for '{name}':"]

    if outgoing:
        lines.append(f"\n  Outgoing ({len(outgoing)}):")
        for ref in sorted(set(outgoing)):
            lines.append(f"    -> {ref}")
    else:
        lines.append("\n  No outgoing references found.")

    if incoming:
        lines.append(f"\n  Incoming ({len(incoming)}):")
        for ref in sorted(set(incoming)):
            lines.append(f"    <- {ref}")
    else:
        lines.append("\n  No incoming references found.")

    return "\n".join(lines)


def _full_reference_graph(scenario) -> str:
    """Build a summary of all cross-references in the scenario."""
    ref_map = _build_reference_map(scenario)
    if not ref_map:
        return "No cross-references found in this scenario."

    lines = ["Cross-reference graph:"]
    for (src_section, src_name), targets in sorted(ref_map.items()):
        if targets:
            targets_str = ", ".join(sorted(targets))
            lines.append(f"  {src_section}.{src_name} -> {targets_str}")

    return "\n".join(lines)


def _build_reference_map(scenario) -> dict[tuple[str, str], list[str]]:
    """Extract cross-section references from a scenario.

    Returns a dict mapping (section, element_name) -> list of referenced names.
    This is a best-effort extraction covering the most important references.
    """
    refs: dict[tuple[str, str], list[str]] = {}

    # Nodes -> features, conditions, vulnerabilities
    for name, node in scenario.nodes.items():
        targets: list[str] = []
        if node.features:
            targets.extend(node.features.keys())
        if node.conditions:
            targets.extend(node.conditions.keys())
        if node.vulnerabilities:
            targets.extend(node.vulnerabilities)
        if targets:
            refs[("nodes", name)] = targets

    # Infrastructure -> nodes, links, dependencies
    for name, infra in scenario.infrastructure.items():
        targets = []
        if infra.links:
            targets.extend(infra.links)
        if infra.dependencies:
            targets.extend(infra.dependencies)
        if targets:
            refs[("infrastructure", name)] = targets

    # Features -> dependencies
    for name, feat in scenario.features.items():
        if feat.dependencies:
            refs[("features", name)] = list(feat.dependencies)

    # Metrics -> conditions
    for name, metric in scenario.metrics.items():
        if metric.condition:
            refs[("metrics", name)] = [metric.condition]

    # Evaluations -> metrics
    for name, ev in scenario.evaluations.items():
        if ev.metrics:
            refs[("evaluations", name)] = list(ev.metrics)

    # TLOs -> evaluations
    for name, tlo in scenario.tlos.items():
        refs[("tlos", name)] = [tlo.evaluation]

    # Goals -> TLOs
    for name, goal in scenario.goals.items():
        if goal.tlos:
            refs[("goals", name)] = list(goal.tlos)

    # Events -> conditions, injects
    for name, event in scenario.events.items():
        targets = []
        if event.conditions:
            targets.extend(event.conditions)
        if event.injects:
            targets.extend(event.injects)
        if targets:
            refs[("events", name)] = targets

    # Scripts -> events
    for name, script in scenario.scripts.items():
        if script.events:
            refs[("scripts", name)] = list(script.events.keys())

    # Stories -> scripts
    for name, story in scenario.stories.items():
        if story.scripts:
            refs[("stories", name)] = list(story.scripts)

    # Relationships -> source, target
    for name, rel in scenario.relationships.items():
        targets = []
        if rel.source:
            targets.append(rel.source)
        if rel.target:
            targets.append(rel.target)
        if targets:
            refs[("relationships", name)] = targets

    # Accounts -> node
    for name, acct in scenario.accounts.items():
        if acct.node:
            refs[("accounts", name)] = [acct.node]

    # Content -> target
    for name, content in scenario.content.items():
        if content.target:
            refs[("content", name)] = [content.target]

    # Agents -> entity, accounts, etc.
    for name, agent in scenario.agents.items():
        targets = []
        if agent.entity:
            targets.append(agent.entity)
        if agent.starting_accounts:
            targets.extend(agent.starting_accounts)
        if targets:
            refs[("agents", name)] = targets

    # Objectives -> agent/entity, targets, success refs, deps
    for name, obj in scenario.objectives.items():
        targets = []
        if obj.agent:
            targets.append(obj.agent)
        if obj.entity:
            targets.append(obj.entity)
        if obj.targets:
            targets.extend(obj.targets)
        if obj.depends_on:
            targets.extend(obj.depends_on)
        if obj.success:
            targets.extend(obj.success.conditions)
            targets.extend(obj.success.metrics)
            targets.extend(obj.success.evaluations)
            targets.extend(obj.success.tlos)
            targets.extend(obj.success.goals)
        if targets:
            refs[("objectives", name)] = targets

    # Injects -> entities
    for name, inject in scenario.injects.items():
        targets = []
        if inject.from_entity:
            targets.append(inject.from_entity)
        if inject.to_entities:
            targets.extend(inject.to_entities)
        if targets:
            refs[("injects", name)] = targets

    return refs


def _build_diagram(scenario) -> str:
    """Build an ASCII topology diagram."""
    from aces.core.sdl.nodes import NodeType

    lines = [f"Topology: {scenario.name}", "=" * 40]

    # Group VMs by their connected switches
    switch_to_vms: dict[str, list[str]] = {}
    unlinked_vms: list[str] = []

    switches = [
        name for name, node in scenario.nodes.items()
        if node.type == NodeType.SWITCH
    ]
    vms = [
        name for name, node in scenario.nodes.items()
        if node.type == NodeType.VM
    ]

    for sw in switches:
        switch_to_vms[sw] = []

    for vm_name in vms:
        infra = scenario.infrastructure.get(vm_name)
        if infra and infra.links:
            for link in infra.links:
                if link in switch_to_vms:
                    switch_to_vms[link].append(vm_name)
        else:
            unlinked_vms.append(vm_name)

    # Render each switch and its connected VMs
    for sw_name in switches:
        connected = switch_to_vms.get(sw_name, [])
        sw_infra = scenario.infrastructure.get(sw_name)
        cidr = ""
        if sw_infra and sw_infra.properties:
            props = sw_infra.properties
            if hasattr(props, "cidr") and props.cidr:
                cidr = f" ({props.cidr})"
            elif isinstance(props, list) and props:
                pass  # complex properties

        sw_node = scenario.nodes.get(sw_name)
        desc = ""
        if sw_node and sw_node.description:
            desc = f" - {sw_node.description}"

        lines.append(f"\n[{sw_name}]{cidr}{desc}")
        if connected:
            for i, vm in enumerate(connected):
                connector = "├── " if i < len(connected) - 1 else "└── "
                vm_node = scenario.nodes.get(vm)
                svc_info = ""
                if vm_node and vm_node.services:
                    svc_names = [s.name for s in vm_node.services if s.name]
                    if svc_names:
                        svc_info = f"  [{', '.join(svc_names)}]"
                lines.append(f"  {connector}{vm}{svc_info}")
        else:
            lines.append("  (no VMs connected)")

    if unlinked_vms:
        lines.append(f"\n[unlinked VMs]")
        for vm in unlinked_vms:
            lines.append(f"  └── {vm}")

    # Show infrastructure dependencies
    deps_found = False
    for name, infra in scenario.infrastructure.items():
        if infra.dependencies:
            if not deps_found:
                lines.append(f"\n--- Dependencies ---")
                deps_found = True
            for dep in infra.dependencies:
                lines.append(f"  {name} --> {dep}")

    return "\n".join(lines)
