"""Shading utilities: declarative node graphs and role-based material targeting."""

from .graph import NodeGraph, NodeGraphError, NodeRef, SocketRef, OWNER_PROP
from .selectors import (
    MaterialRole,
    ObjectInfo,
    RoleMap,
    Selector,
    anime_character_roles,
)

__all__ = [
    "NodeGraph", "NodeGraphError", "NodeRef", "SocketRef", "OWNER_PROP",
    "MaterialRole", "ObjectInfo", "RoleMap", "Selector", "anime_character_roles",
]
