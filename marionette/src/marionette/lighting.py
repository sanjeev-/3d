"""Light wrapper — the object-level counterpart to Camera and Character.

Imports bpy at module level, so this module is only importable inside Blender.
The matching pure-data model lives in ``configs.LightConfig``.
"""

import math
from typing import Optional, Tuple

import bpy
import mathutils

from .configs import LightConfig, LightType
from .mixins import Animatable


class Light(Animatable):
    """Wrapper for a Blender Light Object with animation capabilities."""

    def __init__(self, obj: bpy.types.Object):
        super().__init__(obj)

        if obj.type != "LIGHT":
            raise TypeError(f"Object {obj.name} is not a Light.")

        self.obj = obj
        self.data = obj.data

    @classmethod
    def create(cls, config: LightConfig, collection=None) -> "Light":
        """Create a new light datablock + object and link it to ``collection``."""
        light_data = bpy.data.lights.new(name=config.name, type=config.type.value)
        light_obj = bpy.data.objects.new(name=config.name, object_data=light_data)

        target = collection or bpy.context.collection
        target.objects.link(light_obj)

        light = cls(light_obj)
        light.apply_config(config)
        return light

    def apply_config(self, config: LightConfig):
        """Update the Blender light from a LightConfig model."""
        self.obj.name = config.name
        self.obj.location = config.location
        self.obj.rotation_euler = tuple(math.radians(r) for r in config.rotation)

        # `type` is read-only on some data types until reassigned explicitly.
        if self.data.type != config.type.value:
            self.data.type = config.type.value

        self.data.energy = config.energy
        self.data.color = config.color
        self.data.use_shadow = config.use_shadow

        if config.type == LightType.AREA:
            self.data.size = config.size
            if config.size_y is not None:
                self.data.shape = "RECTANGLE"
                self.data.size_y = config.size_y
        else:
            # Point/spot/sun all expose a soft-size knob under different names.
            if hasattr(self.data, "shadow_soft_size"):
                self.data.shadow_soft_size = config.size

        if config.type == LightType.SPOT:
            self.data.spot_size = math.radians(config.spot_size)
            self.data.spot_blend = config.spot_blend

    def look_at(self, target, roll: float = 0.0):
        """Aim the light's -Z axis at ``target`` (a wrapper, Object, or vector)."""
        if hasattr(target, "obj"):
            point = target.obj.matrix_world.translation
        elif hasattr(target, "matrix_world"):
            point = target.matrix_world.translation
        else:
            point = mathutils.Vector(target)

        direction = point - self.obj.matrix_world.translation
        if direction.length == 0.0:
            return
        self.obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        if roll:
            self.obj.rotation_euler.rotate_axis("Z", math.radians(roll))

    @property
    def energy(self) -> float:
        return self.data.energy

    @energy.setter
    def energy(self, value: float):
        self.data.energy = value

    @property
    def color(self) -> Tuple[float, float, float]:
        return tuple(self.data.color)

    @color.setter
    def color(self, value: Tuple[float, float, float]):
        self.data.color = value

    @property
    def location(self):
        return self.obj.location

    @location.setter
    def location(self, value):
        self.obj.location = value

    @property
    def rotation(self) -> Tuple[float, float, float]:
        """Returns rotation in DEGREES."""
        return tuple(math.degrees(r) for r in self.obj.rotation_euler)

    @rotation.setter
    def rotation(self, value: Tuple[float, float, float]):
        """Sets rotation from DEGREES (converts to radians for Blender)."""
        self.obj.rotation_euler = tuple(math.radians(r) for r in value)


def clear_lights(collection: Optional[bpy.types.Collection] = None) -> int:
    """Remove every light object (and orphaned light data). Returns the count removed.

    Extracted from the ad-hoc "wipe all lights" preamble that light demos repeat.
    """
    removed = 0
    pool = collection.objects if collection else bpy.data.objects
    for obj in list(pool):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)
            removed += 1
    for light_data in list(bpy.data.lights):
        if light_data.users == 0:
            bpy.data.lights.remove(light_data)
    return removed
