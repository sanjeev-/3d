from enum import Enum

class Interpolation(str, Enum):
    LINEAR = "LINEAR"
    BEZIER = "BEZIER"
    CONSTANT = "CONSTANT"
    BACK = "BACK"
    BOUNCE = "BOUNCE"

class BoneTransformType(str, Enum):
    """Transform types for bone animation."""
    LOCATION = "location"
    ROTATION = "rotation"
    ROTATION_QUATERNION = "rotation_quaternion"
    SCALE = "scale"