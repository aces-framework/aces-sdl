"""ACES Scenario Description Language (SDL).

A backend-agnostic scenario specification language ported from the
Open Cyber Range SDL and extended with sections for content, accounts,
relationships, agents, objectives, workflows, and variables.
"""

from importlib import import_module

__all__ = [
    "instantiate_scenario",
    "InstantiatedScenario",
    "parse_sdl",
    "parse_sdl_file",
    "Scenario",
    "SDLError",
    "SDLInstantiationError",
    "SDLParseError",
    "SDLValidationError",
]


def __getattr__(name: str):
    if name in {
        "SDLError",
        "SDLInstantiationError",
        "SDLParseError",
        "SDLValidationError",
    }:
        module = import_module("aces_sdl._errors")
    elif name == "instantiate_scenario":
        module = import_module("aces_sdl.instantiate")
    elif name in {"parse_sdl", "parse_sdl_file"}:
        module = import_module("aces_sdl.parser")
    elif name in {"InstantiatedScenario", "Scenario"}:
        module = import_module("aces_sdl.scenario")
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
