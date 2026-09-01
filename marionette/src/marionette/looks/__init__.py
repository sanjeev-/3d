"""Looks: render styles that span geometry, materials, lighting, passes and comp."""

from .base import (
    BPY_UNAVAILABLE,
    STAGES,
    Look,
    LookContext,
    LookParams,
    LookPipeline,
    LookRequirements,
    LookResult,
    LookValidationError,
)
from .params import CelParams, PBRParams, bridget_preset, zen_preset
from .registry import available_looks, get_look, look_class, register_look

# Importing concrete looks populates the registry.
from .pbr import PBRLook, StudioLook  # noqa: E402,F401

__all__ = [
    "BPY_UNAVAILABLE", "STAGES", "Look", "LookContext", "LookParams", "LookPipeline", "LookRequirements",
    "LookResult", "LookValidationError",
    "CelParams", "PBRParams", "zen_preset", "bridget_preset",
    "register_look", "get_look", "look_class", "available_looks",
    "PBRLook", "StudioLook",
]
