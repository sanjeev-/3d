import bpy
from .types import Interpolation

class Animatable:
    """Mixin to add animation capabilities to any Blender wrapper (Camera, Mesh, Light)."""
    
    def __init__(self, obj: bpy.types.Object):
        self.obj = obj

    def keyframe(self, data_path: str, frame: int, interpolation="LINEAR"):
        """
        Inserts a keyframe. Enhanced to handle nested data paths (e.g., 'dof.focus_distance').
        """
        target = self.obj
        path = data_path
        
        # Check if property exists on Object (location, rotation) 
        # or Data (lens, dof.focus_distance)
        if not hasattr(target, path.split('.')[0]):
            if hasattr(target.data, path.split('.')[0]):
                target = target.data
            else:
                raise AttributeError(f"Property '{path}' not found on {self.obj.name}")

        target.keyframe_insert(data_path=path, frame=frame)
        
        # Set interpolation
        if target.animation_data and target.animation_data.action:
            for fcurve in target.animation_data.action.fcurves:
                if fcurve.data_path == path:
                    for kp in fcurve.keyframe_points:
                        if kp.co.x == frame:
                            val = interpolation.value if hasattr(interpolation, 'value') else interpolation
                            kp.interpolation = val

    def _set_fcurve_interpolation(self, target, data_path, frame, interpolation):
        """Internal helper to find the correct F-Curve and set point interpolation."""
        if not target.animation_data or not target.animation_data.action:
            return

        # Iterate through F-Curves to find the one matching our data_path
        for fcurve in target.animation_data.action.fcurves:
            if fcurve.data_path == data_path:
                # Find the keyframe point at this specific frame
                for kp in fcurve.keyframe_points:
                    if kp.co.x == frame:
                        kp.interpolation = interpolation.value

    def clear_animation(self):
        """Wipes all keyframes from both the object and its underlying data."""
        if self.obj.animation_data:
            self.obj.animation_data_clear()
        if self.obj.data and hasattr(self.obj.data, "animation_data") and self.obj.data.animation_data:
            self.obj.data.animation_data_clear()

    def set_interpolation_range(self, data_path: str, start_frame: int, end_frame: int, interpolation: Interpolation):
        """Utility to set interpolation for all keyframes in a specific range."""
        target = self.obj if hasattr(self.obj, data_path) else self.obj.data
        if not target.animation_data or not target.animation_data.action:
            return

        for fcurve in target.animation_data.action.fcurves:
            if fcurve.data_path == data_path:
                for kp in fcurve.keyframe_points:
                    if start_frame <= kp.co.x <= end_frame:
                        kp.interpolation = interpolation.value