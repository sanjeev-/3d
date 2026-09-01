"""Marionette - Blender rendering framework with Modal cloud GPU support.

Import layering matters here, because two very different interpreters load this
package:

* your local venv, which has modal/click/rich and no bpy
* Blender's bundled Python, which has bpy and none of the cloud stack

So the scene-authoring API (configs, rigs, shading, looks) is imported eagerly —
it needs only pydantic — while the cloud and audio surface resolves lazily on
first attribute access. ``from marionette import Renderer`` still works; it just
no longer drags ``modal`` into a Blender session that will never call it.

Modules that import bpy at module level (Scene, Camera, Character, Light) are
deliberately not re-exported. Import those directly from inside Blender.
"""

from typing import TYPE_CHECKING, Any

__version__ = "0.1.0"

# --- eager: pure-python scene authoring (pydantic only) ----------------------

from .configs import CharacterConfig, HDRIConfig, LightConfig, LightType
from .rigs import (
    ArcRig,
    DirectionProxyRig,
    HDRIRig,
    LightRig,
    SceneBounds,
    ThreePointRig,
    lights_setup_script,
    orbit_positions,
)
from .shading import (
    MaterialRole,
    NodeGraph,
    ObjectInfo,
    RoleMap,
    Selector,
    anime_character_roles,
)
from .looks import (
    CelParams,
    Look,
    LookContext,
    LookParams,
    LookPipeline,
    LookRequirements,
    LookValidationError,
    PBRLook,
    PBRParams,
    StudioLook,
    available_looks,
    bridget_preset,
    get_look,
    register_look,
    zen_preset,
)

# --- lazy: cloud rendering, phonemes, transcription --------------------------

_LAZY = {
    "Renderer": ".render",
    "RenderConfig": ".render",
    "render_frames_remote": ".modal_render",
    "Viseme": ".phonemes",
    "text_to_phonemes": ".phonemes",
    "phonemes_to_visemes": ".phonemes",
    "text_to_visemes": ".phonemes",
    "Word": ".transcribe",
    "transcribe": ".transcribe",
    "transcribe_words": ".transcribe",
}

if TYPE_CHECKING:  # pragma: no cover - for type checkers and IDEs only
    from .modal_render import render_frames_remote
    from .phonemes import Viseme, phonemes_to_visemes, text_to_phonemes, text_to_visemes
    from .render import Renderer, RenderConfig
    from .transcribe import Word, transcribe, transcribe_words


def __getattr__(name: str) -> Any:
    """Resolve heavy optional dependencies on first use (PEP 562)."""
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    try:
        module = import_module(module_name, __name__)
    except ImportError as exc:
        raise ImportError(
            f"{name!r} needs the optional dependency behind "
            f"{module_name.lstrip('.')!r}, which is unavailable in this "
            f"interpreter ({exc})."
        ) from exc

    value = getattr(module, name)
    globals()[name] = value  # cache so later lookups skip __getattr__
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY))


__all__ = [
    # cloud / audio (resolved lazily)
    "Renderer", "RenderConfig", "render_frames_remote",
    "Viseme", "text_to_phonemes", "phonemes_to_visemes", "text_to_visemes",
    "Word", "transcribe", "transcribe_words",
    # configs
    "CharacterConfig", "HDRIConfig", "LightConfig", "LightType",
    # rigs
    "LightRig", "SceneBounds", "ThreePointRig", "ArcRig", "DirectionProxyRig",
    "HDRIRig", "orbit_positions", "lights_setup_script",
    # shading
    "NodeGraph", "MaterialRole", "RoleMap", "Selector", "ObjectInfo",
    "anime_character_roles",
    # looks
    "Look", "LookPipeline", "LookContext", "LookParams", "LookRequirements",
    "LookValidationError", "PBRLook", "StudioLook",
    "CelParams", "PBRParams", "zen_preset", "bridget_preset",
    "register_look", "get_look", "available_looks",
]
