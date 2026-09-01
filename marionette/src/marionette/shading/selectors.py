"""Role-based targeting for materials.

A look cannot hardcode object names — the Bridget rip calls its face mesh
``bgtDR_face`` while the Zenitsu rip calls it ``5_face_0.1_16_16``. Looks target
*roles*; a RoleMap binds roles to the objects of a specific asset.

Everything here is pure: matching is testable without Blender, and
``RoleMap.resolve_scene`` is the only bpy-touching function.
"""

import fnmatch
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


class MaterialRole(str, Enum):
    """Semantic slot a mesh occupies within a character or set."""

    SKIN = "skin"
    FACE = "face"
    HAIR = "hair"
    CLOTH = "cloth"
    EYES = "eyes"
    OUTLINE = "outline"
    LINEART = "lineart"
    SHADOW_PROXY = "shadow_proxy"
    PROP = "prop"
    ENVIRONMENT = "environment"
    DEFAULT = "default"


@dataclass(frozen=True)
class ObjectInfo:
    """Pure snapshot of the object attributes a selector can match against."""

    name: str
    collections: Tuple[str, ...] = ()
    materials: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Selector:
    """Matches objects by exact name, glob pattern, collection, or material."""

    names: Tuple[str, ...] = ()
    patterns: Tuple[str, ...] = ()
    collections: Tuple[str, ...] = ()
    materials: Tuple[str, ...] = ()

    def matches(self, info: ObjectInfo) -> bool:
        if self.names and info.name in self.names:
            return True
        if any(fnmatch.fnmatch(info.name, p) for p in self.patterns):
            return True
        if self.collections and set(self.collections) & set(info.collections):
            return True
        if self.materials and set(self.materials) & set(info.materials):
            return True
        return False

    @property
    def is_empty(self) -> bool:
        return not (self.names or self.patterns or self.collections or self.materials)


class RoleMap:
    """Binds :class:`MaterialRole` values to selectors for one asset."""

    def __init__(self, mapping: Optional[Dict[MaterialRole, Selector]] = None):
        self._mapping: Dict[MaterialRole, Selector] = dict(mapping or {})

    def __contains__(self, role: MaterialRole) -> bool:
        return role in self._mapping

    def __iter__(self):
        return iter(self._mapping.items())

    @property
    def roles(self) -> List[MaterialRole]:
        return list(self._mapping)

    def bind(self, role: MaterialRole, selector: Selector) -> "RoleMap":
        """Attach ``selector`` to ``role``. Chainable."""
        self._mapping[role] = selector
        return self

    def role_for(self, info: ObjectInfo) -> Optional[MaterialRole]:
        """First matching role, in insertion order. None if nothing matches."""
        for role, selector in self._mapping.items():
            if selector.matches(info):
                return role
        return None

    def resolve(self, objects: Iterable[ObjectInfo]) -> Dict[MaterialRole, List[str]]:
        """Group object names by role. Objects matching nothing are dropped."""
        out: Dict[MaterialRole, List[str]] = {role: [] for role in self._mapping}
        for info in objects:
            role = self.role_for(info)
            if role is not None:
                out[role].append(info.name)
        return out

    def resolve_scene(self, scene=None) -> Dict[MaterialRole, List[str]]:
        """Resolve against a live Blender scene. Requires bpy."""
        import bpy  # noqa: PLC0415 - deliberately lazy so this module stays pure

        target = scene or bpy.context.scene
        infos = []
        for obj in target.objects:
            if obj.type != "MESH":
                continue
            materials = tuple(m.name for m in obj.data.materials if m)
            collections = tuple(c.name for c in obj.users_collection)
            infos.append(ObjectInfo(obj.name, collections, materials))
        return self.resolve(infos)


def anime_character_roles() -> RoleMap:
    """A starting RoleMap covering the naming used by common game-rip exports.

    Ordering matters: outline and line-art meshes are duplicates of the body
    meshes, so they must be claimed before the broader body patterns run.
    """
    return RoleMap(
        {
            MaterialRole.OUTLINE: Selector(
                patterns=("* out", "*_outline", "*Outline*"),
            ),
            MaterialRole.LINEART: Selector(
                patterns=("*LINES*", "*_lines", "*lineart*"),
            ),
            MaterialRole.SHADOW_PROXY: Selector(
                patterns=("*shadow*", "*Shadow*"),
            ),
            MaterialRole.EYES: Selector(
                patterns=("*eye*", "*Eye*"),
            ),
            MaterialRole.FACE: Selector(
                patterns=("*face*", "*Face*"),
            ),
            MaterialRole.HAIR: Selector(
                patterns=("*hair*", "*Hair*"),
            ),
            MaterialRole.SKIN: Selector(
                patterns=("*body*", "*Body*", "*hand*", "*Hand*", "*head*"),
            ),
            MaterialRole.CLOTH: Selector(
                patterns=("*cloth*", "*coat*", "*sandal*", "*hood*", "*costume*"),
            ),
        }
    )
