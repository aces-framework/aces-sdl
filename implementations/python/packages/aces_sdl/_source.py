"""Shared Source reference type.

A Source identifies an artifact (VM image, package, template) by
name and version. Supports shorthand (bare string) and longhand
(name + version dict) forms matching OCR SDL conventions.

The Source is backend-agnostic: it could reference a Docker image,
VM template, OVA, AMI, or any provider-specific artifact. Resolution
is delegated to the deployment backend.

When the artifact is a custom-built container image, the optional
``build`` block records its observable build/provenance facts (see
ADR-023 and ``image_provenance``).
"""

from pydantic import Field

from ._base import SDLModel
from .image_provenance import ContainerImageBuildProvenance


class Source(SDLModel):
    """Provider-neutral artifact reference.

    Shorthand: ``source: "package-name"`` (version defaults to ``"*"``).
    Longhand: ``source: {name: "package-name", version: "1.2.3"}``.
    """

    name: str
    version: str = Field(default="*")
    build: ContainerImageBuildProvenance | None = None
