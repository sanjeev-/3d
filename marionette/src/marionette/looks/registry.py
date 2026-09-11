"""Name -> Look registry, so looks can be selected from config or the CLI."""

from typing import Dict, List, Optional, Type

from .base import Look

_REGISTRY: Dict[str, Type[Look]] = {}


def register_look(name: Optional[str] = None):
    """Class decorator registering a Look under ``name`` (defaults to ``cls.name``)."""

    def decorator(cls: Type[Look]) -> Type[Look]:
        key = name or cls.name
        if key in _REGISTRY and _REGISTRY[key] is not cls:
            raise ValueError(f"look {key!r} is already registered to {_REGISTRY[key].__name__}")
        _REGISTRY[key] = cls
        cls.name = key
        return cls

    return decorator


def get_look(name: str, params=None) -> Look:
    """Instantiate a registered look by name."""
    if name not in _REGISTRY:
        raise KeyError(f"unknown look {name!r}; available: {available_looks()}")
    return _REGISTRY[name](params)


def look_class(name: str) -> Type[Look]:
    """Return the registered class without instantiating it."""
    if name not in _REGISTRY:
        raise KeyError(f"unknown look {name!r}; available: {available_looks()}")
    return _REGISTRY[name]


def available_looks() -> List[str]:
    """Sorted list of registered look names."""
    return sorted(_REGISTRY)
