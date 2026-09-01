import math
from enum import Enum
from typing import Tuple, Optional
from pydantic import BaseModel, Field


class HDRIConfig(BaseModel):
    """Configuration for HDRI environment lighting."""

    path: str = Field(..., description="Path to the HDRI image file (.hdr, .exr, etc.)")
    strength: float = Field(
        default=1.0, ge=0.0, description="Intensity multiplier for the HDRI"
    )
    rotation: float = Field(
        default=0.0, description="Rotation angle in degrees around Z-axis"
    )
# Add to configs.py

class CharacterConfig(BaseModel):
    """Configuration for Character (rigged object) loading and setup."""
    
    name: str = Field(..., description="Name for the character in the scene")
    blend_file: str = Field(..., description="Path to the source .blend file")
    object_name: str = Field(..., description="Name of the object/armature in the source file")
    location: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Initial location in world space"
    )
    rotation: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Initial rotation in degrees (Euler angles)"
    )
    scale: Tuple[float, float, float] = Field(
        default=(1.0, 1.0, 1.0), description="Initial scale"
    )
    collection: Optional[str] = Field(
        default=None, description="Collection name in source file (optional)"
    )

class LightType(str, Enum):
    """Blender light data types."""

    POINT = "POINT"
    SUN = "SUN"
    SPOT = "SPOT"
    AREA = "AREA"


class LightConfig(BaseModel):
    """Configuration for a Blender light.

    Pure data: constructing one never touches bpy, so rigs can be planned and
    unit-tested outside Blender and serialized across the Modal boundary.
    """

    name: str = Field(default="Light", description="Object name in the scene")
    type: LightType = Field(default=LightType.POINT, description="Light data type")
    energy: float = Field(default=1000.0, ge=0.0, description="Power (W for point/spot/area, irradiance for sun)")
    color: Tuple[float, float, float] = Field(default=(1.0, 1.0, 1.0), description="Linear RGB")
    location: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="World-space location in meters"
    )
    rotation: Tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Euler rotation in degrees"
    )
    size: float = Field(default=0.1, ge=0.0, description="Shadow soft size / area width")
    size_y: Optional[float] = Field(default=None, description="Area height (rectangle lights)")
    spot_size: float = Field(default=45.0, gt=0.0, description="Spot cone angle in degrees")
    spot_blend: float = Field(default=0.15, ge=0.0, le=1.0, description="Spot edge softness")
    use_shadow: bool = Field(default=True, description="Whether the light casts shadows")

    def scaled(self, factor: float) -> "LightConfig":
        """Return a copy with energy multiplied by ``factor``."""
        return self.model_copy(update={"energy": self.energy * factor})
