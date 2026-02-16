import bpy
import math
from enum import Enum
from typing import Tuple, Optional
from pydantic import BaseModel, Field
from .mixins import Animatable

class CameraType(str, Enum):
    PERSP = "PERSP"
    ORTHO = "ORTHO"
    PANO = "PANO"

class DOFConfig(BaseModel):
    enabled: bool = True
    focus_distance: float = 10.0
    fstop: float = 2.8
    focus_object: Optional[str] = None 

class CameraConfig(BaseModel):
    name: str = "Camera"
    type: CameraType = CameraType.PERSP
    lens: float = Field(default=50.0, ge=1.0)
    clip_start: float = 0.1
    clip_end: float = 1000.0
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0) # meters
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0) # degrees
    dof: DOFConfig = DOFConfig()

class Camera(Animatable):
    """Wrapper for a Blender Camera Object with Animation capabilities."""
    
    def __init__(self, obj: bpy.types.Object):
        super().__init__(obj) 
        
        if obj.type != 'CAMERA':
            raise TypeError(f"Object {obj.name} is not a Camera.")
        
        self.obj = obj
        self.data = obj.data

    def apply_config(self, config: CameraConfig):
        """Updates the Blender object based on a CameraConfig model."""
        self.obj.name = config.name
        self.obj.location = config.location
        self.obj.rotation_euler = tuple(math.radians(r) for r in config.rotation)
        
        self.data.type = config.type.value
        self.data.clip_start = config.clip_start
        self.data.clip_end = config.clip_end
        
        if config.type == CameraType.PERSP:
            self.data.lens = config.lens
            
        self.data.dof.use_dof = config.dof.enabled
        self.data.dof.focus_distance = config.dof.focus_distance
        self.data.dof.aperture_fstop = config.dof.fstop

    def focus_on(self, target, frame: Optional[int] = None, interpolation=None):
        """
        Sets the focus distance to match the target. 
        If frame is provided, it inserts a keyframe.
        """
        dist = self.get_distance_to(target)
        self.focus_distance = dist
        
        if frame is not None:
            self.keyframe("dof.focus_distance", frame, interpolation or "BEZIER")


    def get_distance_to(self, target) -> float:
        """Calculates distance from camera to a Character wrapper or Blender Object."""
        # Extract location from Character wrapper or Blender Object
        target_obj = target.obj if hasattr(target, 'obj') else target
        
        # Calculate Euclidean distance
        dist = (self.obj.location - target_obj.location).length
        return dist
        
    @property
    def focus_distance(self):
        return self.data.dof.focus_distance

    @focus_distance.setter
    def focus_distance(self, value):
        self.data.dof.use_dof = True
        self.data.dof.focus_distance = value


    @property
    def location(self):
        return self.obj.location

    @location.setter
    def location(self, value):
        self.obj.location = value

    @property
    def rotation(self):
        """Returns rotation in DEGREES."""
        return tuple(math.degrees(r) for r in self.obj.rotation_euler)

    @rotation.setter
    def rotation(self, value):
        """Sets rotation from DEGREES (converts to radians for Blender)."""
        self.obj.rotation_euler = tuple(math.radians(r) for r in value)

    @property
    def lens(self):
        """Accesses the focal length from the Camera Data block."""
        return self.data.lens

    @lens.setter
    def lens(self, value):
        self.data.lens = value