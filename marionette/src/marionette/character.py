import bpy
import math
from typing import Tuple, Union
from .mixins import Animatable
from .configs import CharacterConfig
from .types import Interpolation, BoneTransformType


class Character(Animatable):
    """Wrapper for a Blender Character (rigged object) with Animation capabilities."""
    
    def __init__(self, obj: bpy.types.Object):
        super().__init__(obj)
        
        self.obj = obj
        self.data = obj.data
        
        # Find the armature - could be the object itself or via modifier
        self.armature = None
        if obj.type == "ARMATURE":
            self.armature = obj
        else:
            # Check for armature modifier
            for modifier in obj.modifiers:
                if modifier.type == "ARMATURE" and modifier.object:
                    self.armature = modifier.object
                    break
    
    def apply_config(self, config: CharacterConfig):
        """Updates the Blender object based on a CharacterConfig model."""
        self.obj.name = config.name
        self.obj.location = config.location
        self.obj.rotation_euler = tuple(math.radians(r) for r in config.rotation)
        self.obj.scale = config.scale
    
    @property
    def location(self) -> Tuple[float, float, float]:
        """Returns location as a tuple."""
        return tuple(self.obj.location)
    
    @location.setter
    def location(self, value: Tuple[float, float, float]):
        """Sets location from a tuple."""
        self.obj.location = value
    
    @property
    def rotation(self) -> Tuple[float, float, float]:
        """Returns rotation in DEGREES."""
        return tuple(math.degrees(r) for r in self.obj.rotation_euler)
    
    @rotation.setter
    def rotation(self, value: Tuple[float, float, float]):
        """Sets rotation from DEGREES (converts to radians for Blender)."""
        self.obj.rotation_euler = tuple(math.radians(r) for r in value)
    
    @property
    def scale(self) -> Tuple[float, float, float]:
        """Returns scale as a tuple."""
        return tuple(self.obj.scale)
    
    @scale.setter
    def scale(self, value: Tuple[float, float, float]):
        """Sets scale from a tuple."""
        self.obj.scale = value
    
    def animate_bone(
            self,
            bone_name: str,
            frame: int,
            transform_type: BoneTransformType,
            value: Union[Tuple[float, float, float], Tuple[float, float, float, float]],
            interpolation: Interpolation = Interpolation.LINEAR,
        ):
            """
            Animates a bone's transform property.
            
            Args:
                bone_name: Name of the bone to animate
                transform_type: One of BoneTransformType enum values
                value: Value to set (3-tuple for loc/rot/scale, 4-tuple for quaternion)
                interpolation: Interpolation type for the keyframe
            """
            # 1. Validation: Check if armature exists
            if not self.armature:
                raise ValueError(f"Character {self.obj.name} has no armature. Cannot animate bones.")
            
            # 2. Validation: Check if bone exists in the pose
            if bone_name not in self.armature.pose.bones:
                raise ValueError(f"Bone '{bone_name}' not found in armature {self.armature.name}")
            
            bone = self.armature.pose.bones[bone_name]
            data_path = ""

            # 3. Set the value based on Enum and define the data_path for keyframing
            if transform_type == BoneTransformType.LOCATION:
                if len(value) != 3:
                    raise ValueError("Location requires 3 values (x, y, z)")
                bone.location = value
                data_path = f'pose.bones["{bone_name}"].location'

            elif transform_type == BoneTransformType.ROTATION:
                if len(value) != 3:
                    raise ValueError("Rotation requires 3 values (Euler angles in radians)")
                bone.rotation_euler = value
                data_path = f'pose.bones["{bone_name}"].rotation_euler'

            elif transform_type == BoneTransformType.ROTATION_QUATERNION:
                if len(value) != 4:
                    raise ValueError("Rotation quaternion requires 4 values (w, x, y, z)")
                bone.rotation_quaternion = value
                data_path = f'pose.bones["{bone_name}"].rotation_quaternion'

            elif transform_type == BoneTransformType.SCALE:
                if len(value) != 3:
                    raise ValueError("Scale requires 3 values")
                bone.scale = value
                data_path = f'pose.bones["{bone_name}"].scale'
            
            else:
                raise ValueError(f"Unsupported transform type: {transform_type}")

            # 4. Insert the keyframe into the Armature object
            # We call this on the armature because the data_path starts from the armature level
            self.armature.keyframe_insert(data_path=data_path, frame=frame)
            
            # 5. Apply interpolation (Bezier, Linear, Constant, etc.)
            self._set_bone_fcurve_interpolation(data_path, frame, interpolation)
    
    def _set_bone_fcurve_interpolation(
        self, data_path: str, frame: int, interpolation: Interpolation
    ):
        """Internal helper to set interpolation on bone F-Curves."""
        if not self.armature.animation_data or not self.armature.animation_data.action:
            return
        
        for fcurve in self.armature.animation_data.action.fcurves:
            if fcurve.data_path == data_path:
                for kp in fcurve.keyframe_points:
                    if kp.co.x == frame:
                        kp.interpolation = interpolation.value