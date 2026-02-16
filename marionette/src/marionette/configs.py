import math
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