"""
Blender integration service for creating and modifying .blend files.
"""

import os
import subprocess
from pathlib import Path
from django.conf import settings


class BlenderService:
    """
    Service for creating and manipulating Blender files.
    """

    @staticmethod
    def create_scene_blend_file(scene):
        """
        Create a new Blender file for a scene.

        Args:
            scene: Scene model instance
        """
        # Ensure directory exists
        blend_path = Path(settings.MEDIA_ROOT) / f"blender_files/projects/{scene.project.id}/scenes"
        blend_path.mkdir(parents=True, exist_ok=True)

        blend_file = blend_path / f"{scene.id}.blend"

        # Create Python script to initialize Blender scene
        init_script = f"""
import bpy

# Clear default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Set up camera
bpy.ops.object.camera_add(location=(7, -7, 5))
camera = bpy.context.active_object
camera.name = '{scene.camera_name}'
bpy.context.scene.camera = camera

# Set up lighting
bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))
light = bpy.context.active_object
light.name = 'MainLight'
light.data.energy = 2.0

# Set render settings
scene_settings = bpy.context.scene
scene_settings.render.engine = '{scene.project.render_engine}'
scene_settings.render.resolution_x = {scene.project.resolution_width}
scene_settings.render.resolution_y = {scene.project.resolution_height}
scene_settings.render.fps = {scene.project.fps}
scene_settings.frame_start = {scene.frame_start}
scene_settings.frame_end = {scene.frame_end}

# Save
bpy.ops.wm.save_as_mainfile(filepath='{blend_file}')
"""

        # Execute Blender to create the file
        try:
            subprocess.run([
                'blender',
                '--background',
                '--python-expr', init_script
            ], check=True, capture_output=True)

            # Update scene model with blend file path
            scene.blend_file = f"blender_files/projects/{scene.project.id}/scenes/{scene.id}.blend"
            scene.save()

        except subprocess.CalledProcessError as e:
            print(f"Error creating Blender file: {e}")
            # In production, log this error properly

    @staticmethod
    def add_object_to_scene(scene, scene_object):
        """
        Add an object to a Blender scene.

        Args:
            scene: Scene model instance
            scene_object: SceneObject model instance
        """
        if not scene.blend_file:
            return

        blend_path = Path(settings.MEDIA_ROOT) / scene.blend_file

        if not blend_path.exists():
            return

        # Create Python script to add object
        script = f"""
import bpy

# Add object based on type
if '{scene_object.object_type}' == 'ASSET' or '{scene_object.object_type}' == 'CHARACTER':
    # Link/append from blend file
    # In production, implement proper asset linking
    bpy.ops.mesh.primitive_cube_add(location=({scene_object.position_x}, {scene_object.position_y}, {scene_object.position_z}))
    obj = bpy.context.active_object
else:
    bpy.ops.mesh.primitive_cube_add(location=({scene_object.position_x}, {scene_object.position_y}, {scene_object.position_z}))
    obj = bpy.context.active_object

obj.name = '{scene_object.name}'
obj.rotation_euler = ({scene_object.rotation_x}, {scene_object.rotation_y}, {scene_object.rotation_z})
obj.scale = ({scene_object.scale_x}, {scene_object.scale_y}, {scene_object.scale_z})

# Save
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
"""

        try:
            subprocess.run([
                'blender',
                str(blend_path),
                '--background',
                '--python-expr', script
            ], check=True, capture_output=True)

            # Increment version
            scene.blend_file_version += 1
            scene.save()

        except subprocess.CalledProcessError as e:
            print(f"Error adding object to Blender scene: {e}")

    @staticmethod
    def update_object_in_scene(scene, scene_object):
        """
        Update an object's transform in a Blender scene.

        Args:
            scene: Scene model instance
            scene_object: SceneObject model instance
        """
        if not scene.blend_file:
            return

        blend_path = Path(settings.MEDIA_ROOT) / scene.blend_file

        if not blend_path.exists():
            return

        script = f"""
import bpy

# Find object by name
obj = bpy.data.objects.get('{scene_object.name}')

if obj:
    obj.location = ({scene_object.position_x}, {scene_object.position_y}, {scene_object.position_z})
    obj.rotation_euler = ({scene_object.rotation_x}, {scene_object.rotation_y}, {scene_object.rotation_z})
    obj.scale = ({scene_object.scale_x}, {scene_object.scale_y}, {scene_object.scale_z})

    # Save
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
"""

        try:
            subprocess.run([
                'blender',
                str(blend_path),
                '--background',
                '--python-expr', script
            ], check=True, capture_output=True)

            scene.blend_file_version += 1
            scene.save()

        except subprocess.CalledProcessError as e:
            print(f"Error updating object in Blender scene: {e}")

    @staticmethod
    def export_scene_preview(scene, output_path):
        """
        Render a preview image of a scene.

        Args:
            scene: Scene model instance
            output_path: Path to save preview image
        """
        if not scene.blend_file:
            return False

        blend_path = Path(settings.MEDIA_ROOT) / scene.blend_file

        if not blend_path.exists():
            return False

        try:
            subprocess.run([
                'blender',
                str(blend_path),
                '--background',
                '--render-output', str(output_path),
                '--render-frame', str(scene.frame_start),
            ], check=True, capture_output=True)

            return True

        except subprocess.CalledProcessError:
            return False
