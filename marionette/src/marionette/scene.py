import math
import bpy
import os
from typing import List, Optional
from .character import Character
from .configs import CharacterConfig
from .camera import Camera, CameraConfig
from .camera_movements import CameraMovement
from .configs import HDRIConfig, LightConfig
from .lighting import Light
from .rigs import HDRIRig, LightRig, SceneBounds

class Scene:
    def __init__(self, filepath=None):
            if filepath:
                if not os.path.exists(filepath):
                    raise FileNotFoundError(f"Blend file not found: {filepath}")
                bpy.ops.wm.open_mainfile(filepath=filepath)
            
            self.scene = bpy.context.scene

    def add_camera(self, config: CameraConfig) -> Camera:
        """Blueprints a new camera, links it to the scene, and returns a Camera object."""
        # Create data and object
        cam_data = bpy.data.cameras.new(config.name)
        cam_obj = bpy.data.objects.new(config.name, cam_data)
        
        # Link to collection
        bpy.context.collection.objects.link(cam_obj)
        
        # Wrap and apply settings
        camera = Camera(cam_obj)
        camera.apply_config(config)
        
        # Make active in scene
        self.scene.camera = cam_obj
        
        # Force matrix calculation
        bpy.context.view_layer.update()
        
        return camera

    def setup_cycles(self, res=512, samples=128):
        render = self.scene.render
        render.engine = 'CYCLES'
        render.resolution_x = res
        render.resolution_y = res
        
        self.scene.cycles.samples = samples
        self.scene.cycles.device = 'GPU'
        
        # Setup Metal for Mac
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'METAL'
        for d in prefs.get_devices_for_type('METAL'):
            d.use = True

    def add_light(self, config: LightConfig) -> Light:
        """Create a light from a config, link it to the scene, and return the wrapper."""
        return Light.create(config)

    def apply_rig(self, rig: LightRig, bounds: Optional[SceneBounds] = None) -> List[Light]:
        """Apply a LightRig to this scene. Returns the lights it created."""
        return rig.apply(self.scene, bounds=bounds)

    def set_hdri(self, config: HDRIConfig):
        """Set an HDRI environment map for the scene.

        Delegates to :class:`~marionette.rigs.HDRIRig`, which builds the world
        node tree through the declarative NodeGraph builder. Rebuilding is
        idempotent: re-applying replaces the previously built nodes instead of
        accumulating duplicates.

        Args:
            config: HDRIConfig containing path, strength, and rotation settings

        Raises:
            FileNotFoundError: If the HDRI file doesn't exist
        """
        HDRIRig(config).apply(self.scene)

    def add_character(self, config: CharacterConfig) -> Character:
        """
        Loads a character (rigged object) from a .blend file and adds it to the scene.
        
        Args:
            config: CharacterConfig containing blend file path, object name, and transform settings
        
        Returns:
            Character wrapper object
        
        Raises:
            FileNotFoundError: If the blend file doesn't exist
            ValueError: If the object is not found in the source file
        """
        if not os.path.exists(config.blend_file):
            raise FileNotFoundError(f"Blend file not found: {config.blend_file}")
        
        # Use Blender's append operator to load the object
        # filepath format: "/path/to/file.blend/Object/ObjectName"
        # directory: "Object"
        # filename: name of the item to append
        
        if config.collection:
            # Append from collection
            directory = "Collection"
            filename = config.collection
            filepath = os.path.join(config.blend_file, directory, filename)
            try:
                bpy.ops.wm.append(
                    filepath=filepath,
                    directory=directory,
                    filename=filename,
                )
            except RuntimeError as e:
                raise ValueError(f"Failed to append collection '{config.collection}' from {config.blend_file}: {e}")
        else:
            filename = config.object_name
            directory = os.path.join(config.blend_file, "Object") + os.sep
            filepath = os.path.join(directory, filename)
            
            try:
                bpy.ops.wm.append(
                    filepath=filepath,
                    directory=directory,
                    filename=filename,
                )
            except RuntimeError as e:
                raise ValueError(f"Failed to append object '{config.object_name}' from {config.blend_file}: {e}")
        
        # Find the appended object
        if config.object_name not in bpy.data.objects:
            # Try to find by name (might have been renamed)
            found_obj = None
            for obj in bpy.data.objects:
                if obj.name.startswith(config.object_name) or config.object_name in obj.name:
                    found_obj = obj
                    break
            if not found_obj:
                raise ValueError(f"Object '{config.object_name}' not found after appending from {config.blend_file}")
            obj = found_obj
        else:
            obj = bpy.data.objects[config.object_name]
        
        # Link to active collection if not already linked
        if obj.name not in [o.name for o in bpy.context.collection.objects]:
            bpy.context.collection.objects.link(obj)
        
        # Rename to config name
        obj.name = config.name
        
        # Create Character wrapper and apply config
        character = Character(obj)
        character.apply_config(config)
        
        # Force matrix calculation
        bpy.context.view_layer.update()
        
        return character


    def set_timeline(self, start: int, end: int, fps: int = 24):
        self.scene.frame_start = start
        self.scene.frame_end = end
        self.scene.render.fps = fps

    def apply_movement(self, camera: Camera, movement: CameraMovement):
        movement.apply(camera)

    @property
    def current_frame(self):
        return self.scene.frame_current

    @current_frame.setter
    def current_frame(self, value: int):
        self.scene.frame_set(value)
