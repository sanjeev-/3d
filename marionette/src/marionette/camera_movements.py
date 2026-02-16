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
            
            con = camera.obj.constraints.get(constraint_name)
            if not con:
                con = camera.obj.constraints.new(type='TRACK_TO')
                con.name = constraint_name
                
            con.target = target_obj
            con.track_axis = 'TRACK_NEGATIVE_Z'
            con.up_axis = 'UP_Y'
            
            # Set influence to 0 at start_frame for smooth transition
            con.influence = 0.0
            camera.obj.keyframe_insert(
                data_path=f'constraints["{constraint_name}"].influence', 
                frame=start_frame
            )
            
            # Set influence to 1.0 at end_frame
            con.influence = 1.0
            camera.obj.keyframe_insert(
                data_path=f'constraints["{constraint_name}"].influence', 
                frame=end_frame
            )
            
            # Apply interpolation to constraint influence keyframes
            self._set_constraint_influence_interpolation(camera, constraint_name, start_frame, end_frame)
    
    def _set_constraint_influence_interpolation(self, camera: Camera, constraint_name: str, start_frame: int, end_frame: int):
        """Set interpolation on constraint influence keyframes."""
        if not camera.obj.animation_data or not camera.obj.animation_data.action:
            return
        
        data_path = f'constraints["{constraint_name}"].influence'
        for fcurve in camera.obj.animation_data.action.fcurves:
            if fcurve.data_path == data_path:
                for kp in fcurve.keyframe_points:
                    if kp.co.x == start_frame or kp.co.x == end_frame:
                        kp.interpolation = self.interpolation.value
    
    def _disable_track_to(self, camera: Camera, frame: int):
        """Disable the Track To constraint at a specific frame."""
        constraint_name = "Marionette_LookAt"
        con = camera.obj.constraints.get(constraint_name)
        if con:
            con.influence = 0.0
            camera.obj.keyframe_insert(
                data_path=f'constraints["{constraint_name}"].influence', 
                frame=frame
            )
            # Apply interpolation
            if camera.obj.animation_data and camera.obj.animation_data.action:
                data_path = f'constraints["{constraint_name}"].influence'
                for fcurve in camera.obj.animation_data.action.fcurves:
                    if fcurve.data_path == data_path:
                        for kp in fcurve.keyframe_points:
                            if kp.co.x == frame:
                                kp.interpolation = self.interpolation.value

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
        constraint_name = "Marionette_LookAt"
        previous_has_look_at = False
        
        for i, wp in enumerate(self.waypoints):
            # 1. Handle Location
            if wp.location is not None:
                camera.location = wp.location
                camera.keyframe("location", frame=wp.frame, interpolation=self.interpolation)
            
            # 2. Handle Lens (Zoom)
            if wp.lens is not None:
                camera.lens = wp.lens
                camera.keyframe("lens", frame=wp.frame, interpolation=self.interpolation)
                
            # 3. Handle Rotation or tracking
            if wp.look_at:
                # Find the start frame for smooth transition
                # If this is the first waypoint, use start_frame
                # Otherwise, use the previous waypoint's frame
                if i == 0:
                    start_frame = self.start_frame
                else:
                    start_frame = self.waypoints[i - 1].frame
                
                # If previous waypoint didn't have look_at, ensure constraint is disabled at start_frame
                if not previous_has_look_at and i > 0:
                    self._disable_track_to(camera, start_frame)
                
                self._setup_track_to(camera, wp.look_at, start_frame, wp.frame)
                previous_has_look_at = True
            else:
                # No look_at for this waypoint
                # If previous waypoint had look_at, disable constraint at this frame first
                if previous_has_look_at:
                    self._disable_track_to(camera, wp.frame)
                    # Ensure constraint is disabled before keyframing rotation
                    con = camera.obj.constraints.get(constraint_name)
                    if con:
                        con.influence = 0.0
                
                # Explicitly set and keyframe rotation
                if wp.rotation is not None:
                    camera.rotation = wp.rotation
                # Always keyframe rotation to ensure smooth transitions
                # This preserves the current rotation if not explicitly set
                camera.keyframe("rotation_euler", frame=wp.frame, interpolation=self.interpolation)
                previous_has_look_at = False