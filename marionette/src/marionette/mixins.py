import bpy

from .types import Interpolation


def iter_fcurves(action):
    """Yield every F-Curve in ``action``, across both Blender action layouts.

    Blender 4.4 replaced ``Action.fcurves`` with layered/slotted actions, where
    curves live at ``action.layers[].strips[].channelbags[].fcurves``. Accessing
    ``.fcurves`` directly raises AttributeError on 4.4+, which silently broke
    every interpolation setter in this package. Route all access through here.
    """
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        yield from legacy
        return

    for layer in getattr(action, "layers", ()):
        for strip in getattr(layer, "strips", ()):
            for channelbag in getattr(strip, "channelbags", ()):
                yield from channelbag.fcurves


def resolve_target(obj: bpy.types.Object, data_path: str):
    """Return whichever of ``obj`` / ``obj.data`` owns ``data_path``.

    Handles nested paths (``dof.focus_distance``) and subscripted ones
    (``constraints["X"].influence``) by testing only the leading attribute —
    ``hasattr(obj, "dof.focus_distance")`` is always False and would send every
    nested path to ``obj.data`` regardless of where it actually lives.
    """
    root = data_path.split(".", 1)[0].split("[", 1)[0]

    if hasattr(obj, root):
        return obj
    data = getattr(obj, "data", None)
    if data is not None and hasattr(data, root):
        return data
    raise AttributeError(f"Property '{data_path}' not found on {obj.name}")


def set_fcurve_interpolation(action, data_path: str, interpolation, frames=None):
    """Set interpolation on keyframes of ``data_path``.

    Args:
        frames: Restrict to these frame numbers; None means every keyframe.
    """
    value = interpolation.value if hasattr(interpolation, "value") else interpolation
    for fcurve in iter_fcurves(action):
        if fcurve.data_path != data_path:
            continue
        for point in fcurve.keyframe_points:
            if frames is None or point.co.x in frames:
                point.interpolation = value


class Animatable:
    """Mixin to add animation capabilities to any Blender wrapper (Camera, Mesh, Light)."""

    def __init__(self, obj: bpy.types.Object):
        self.obj = obj

    def keyframe(self, data_path: str, frame: int, interpolation="LINEAR"):
        """Insert a keyframe, handling nested data paths (e.g. 'dof.focus_distance')."""
        target = resolve_target(self.obj, data_path)
        target.keyframe_insert(data_path=data_path, frame=frame)

        if target.animation_data and target.animation_data.action:
            set_fcurve_interpolation(
                target.animation_data.action, data_path, interpolation, frames={frame}
            )

    def _set_fcurve_interpolation(self, target, data_path, frame, interpolation):
        """Internal helper to find the correct F-Curve and set point interpolation."""
        if not target.animation_data or not target.animation_data.action:
            return
        set_fcurve_interpolation(
            target.animation_data.action, data_path, interpolation, frames={frame}
        )

    def clear_animation(self):
        """Wipes all keyframes from both the object and its underlying data."""
        if self.obj.animation_data:
            self.obj.animation_data_clear()
        if (
            self.obj.data
            and hasattr(self.obj.data, "animation_data")
            and self.obj.data.animation_data
        ):
            self.obj.data.animation_data_clear()

    def set_interpolation_range(
        self,
        data_path: str,
        start_frame: int,
        end_frame: int,
        interpolation: Interpolation,
    ):
        """Set interpolation for all keyframes of ``data_path`` in a frame range."""
        target = resolve_target(self.obj, data_path)
        if not target.animation_data or not target.animation_data.action:
            return

        value = interpolation.value if hasattr(interpolation, "value") else interpolation
        for fcurve in iter_fcurves(target.animation_data.action):
            if fcurve.data_path != data_path:
                continue
            for point in fcurve.keyframe_points:
                if start_frame <= point.co.x <= end_frame:
                    point.interpolation = value
