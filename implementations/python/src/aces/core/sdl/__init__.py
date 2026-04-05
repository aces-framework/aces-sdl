"""Backward-compatible SDL namespace."""

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
