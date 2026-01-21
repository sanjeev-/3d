import bpy
from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from .camera import Camera
from .types import Interpolation

class Waypoint(BaseModel):
    """A single point in time and space for a camera path."""
    frame: int
    location: Optional[Tuple[float, float, float]] = None
    rotation: Optional[Tuple[float, float, float]] = None
    lens: Optional[float] = None
    look_at: Optional[str] = None

class CameraMovement(ABC):
    """Abstract base for all camera movement strategies."""
    def __init__(self, start_frame: int, end_frame: int, interpolation: Interpolation = Interpolation.LINEAR):
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.interpolation = interpolation

    @abstractmethod
    def apply(self, camera: Camera):
        """Apply the movement logic to the camera."""
        pass

    def _get_or_create_constraint(self, camera: Camera, constraint_name: str = "Marionette_LookAt"):
        """Get or create a Track To constraint on the camera."""
        con = camera.obj.constraints.get(constraint_name)
        if not con:
            con = camera.obj.constraints.new(type='TRACK_TO')
            con.name = constraint_name
            con.track_axis = 'TRACK_NEGATIVE_Z'
            con.up_axis = 'UP_Y'
        return con
    
    def _set_constraint_influence(self, camera: Camera, constraint_name: str, frame: int, influence: float):
        """Set constraint influence at a specific frame."""
        con = camera.obj.constraints.get(constraint_name)
        if con:
            con.influence = influence
            camera.obj.keyframe_insert(
                data_path=f'constraints["{constraint_name}"].influence',
                frame=frame
            )
    
    def _setup_track_to(self, camera: Camera, target_name: str, start_frame: int, end_frame: int):
        """Helper to create or update a Track To constraint for 'look_at' functionality.
        
        Args:
            camera: The camera object
            target_name: Name of the object to track
            start_frame: Frame where tracking should start (influence 0)
            end_frame: Frame where tracking should be active (influence 1)
        """
        if target_name not in bpy.data.objects:
            print(f"Warning: Target {target_name} not found.")
            return
            
        target_obj = bpy.data.objects[target_name]
        constraint_name = "Marionette_LookAt"
        
        con = self._get_or_create_constraint(camera, constraint_name)
        con.target = target_obj
        
        # Set influence to 0 at start_frame for smooth transition
        self._set_constraint_influence(camera, constraint_name, start_frame, 0.0)
        
        # Set influence to 1.0 at end_frame
        self._set_constraint_influence(camera, constraint_name, end_frame, 1.0)

class DollyMovement(CameraMovement):
    """Moves camera from point A to point B."""
    def __init__(self, start_frame: int, end_frame: int, start_pos: Tuple, end_pos: Tuple, **kwargs):
        super().__init__(start_frame, end_frame, **kwargs)
        self.start_pos = start_pos
        self.end_pos = end_pos

    def apply(self, camera: Camera):
        camera.location = self.start_pos
        camera.keyframe("location", frame=self.start_frame, interpolation=self.interpolation)
        camera.keyframe("rotation_euler", frame=self.start_frame, interpolation=self.interpolation)
        
        camera.location = self.end_pos
        camera.keyframe("location", frame=self.end_frame, interpolation=self.interpolation)

class GenericCameraMovement(CameraMovement):
    """Waypoint-based system handling position, zoom, and object tracking."""
    def __init__(self, waypoints: List[Waypoint], interpolation: Interpolation = Interpolation.BEZIER):
        self.waypoints = sorted(waypoints, key=lambda x: x.frame)
        super().__init__(self.waypoints[0].frame, self.waypoints[-1].frame, interpolation)

    def apply(self, camera: Camera):
        """Apply waypoint-based camera movement with smooth transitions."""
        constraint_name = "Marionette_LookAt"
        prev_waypoint = None
        
        for i, wp in enumerate(self.waypoints):
            # Determine transition start frame (previous waypoint or movement start)
            transition_start = self.waypoints[i - 1].frame if i > 0 else self.start_frame
            
            # 1. Handle Location
            if wp.location is not None:
                camera.location = wp.location
                camera.keyframe("location", frame=wp.frame, interpolation=self.interpolation)
            
            # 2. Handle Lens (Zoom)
            if wp.lens is not None:
                camera.lens = wp.lens
                camera.keyframe("lens", frame=wp.frame, interpolation=self.interpolation)
            
            # 3. Handle Rotation/Tracking with smooth transitions
            prev_was_tracking = prev_waypoint is not None and prev_waypoint.look_at is not None
            curr_is_tracking = wp.look_at is not None
            
            if curr_is_tracking:
                # Enable tracking: transition constraint influence from 0 to 1
                self._setup_track_to(camera, wp.look_at, transition_start, wp.frame)
            elif prev_was_tracking:
                # Disable tracking: transition constraint influence from 1 to 0
                self._set_constraint_influence(camera, constraint_name, transition_start, 1.0)
                self._set_constraint_influence(camera, constraint_name, wp.frame, 0.0)
            
            # Set explicit rotation if provided (look_at takes precedence)
            if wp.rotation is not None and not curr_is_tracking:
                camera.rotation = wp.rotation
                camera.keyframe("rotation_euler", frame=wp.frame, interpolation=self.interpolation)
            
            prev_waypoint = wp