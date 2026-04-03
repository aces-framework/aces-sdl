"""ACES Scenario Description Language (SDL).

A backend-agnostic scenario specification language ported from the
Open Cyber Range SDL and extended with sections for content, accounts,
relationships, agents, objectives, workflows, and variables.

Public API:
    parse_sdl(content) -> Scenario
    parse_sdl_file(path) -> Scenario
    instantiate_scenario(scenario, parameters=None, profile=None) -> InstantiatedScenario
    Scenario — top-level model (21 sections)
    InstantiatedScenario — fully concrete scenario ready for compilation
    SDLParseError — YAML/structural errors
    SDLValidationError — semantic validation errors
    SDLInstantiationError — parameter binding / concrete instantiation errors
"""

from aces.core.sdl._errors import (
    SDLError,
    SDLInstantiationError,
    SDLParseError,
    SDLValidationError,
)
from aces.core.sdl.instantiate import instantiate_scenario
from aces.core.sdl.parser import parse_sdl, parse_sdl_file
from aces.core.sdl.scenario import InstantiatedScenario, Scenario

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
