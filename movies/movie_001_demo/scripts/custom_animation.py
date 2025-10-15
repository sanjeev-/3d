"""
Custom animation script for Demo Movie.

This script can be run inside Blender to set up custom animations
or procedural content that can't be easily defined in the YAML.

Usage:
    Run this script inside Blender's scripting workspace or via:
    blender movie.blend --python custom_animation.py
"""

import bpy
import math


def create_animated_cube(name="AnimatedCube", location=(0, 0, 0)):
    """
    Create a cube with animated rotation and scale.

    Args:
        name: Name for the cube object
        location: Initial location (x, y, z)

    Returns:
        The created cube object
    """
    # Create cube
    bpy.ops.mesh.primitive_cube_add(location=location)
    cube = bpy.context.active_object
    cube.name = name

    # Set up material
    mat = bpy.data.materials.new(name=f"{name}_Material")
    mat.use_nodes = True
    cube.data.materials.append(mat)

    # Get material nodes
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.8, 0.2, 0.2, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.5
        bsdf.inputs["Roughness"].default_value = 0.2

    # Animate rotation
    cube.rotation_euler = (0, 0, 0)
    cube.keyframe_insert(data_path="rotation_euler", frame=1)

    cube.rotation_euler = (0, 0, math.pi * 2)
    cube.keyframe_insert(data_path="rotation_euler", frame=120)

    # Animate scale
    cube.scale = (1, 1, 1)
    cube.keyframe_insert(data_path="scale", frame=1)

    cube.scale = (2, 2, 2)
    cube.keyframe_insert(data_path="scale", frame=60)

    cube.scale = (1, 1, 1)
    cube.keyframe_insert(data_path="scale", frame=120)

    # Set interpolation to smooth
    for fcurve in cube.animation_data.action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = 'BEZIER'

    return cube


def setup_camera(location=(7, -7, 5), target=(0, 0, 0)):
    """
    Set up a camera looking at a target.

    Args:
        location: Camera location
        target: Point to look at
    """
    # Create camera
    bpy.ops.object.camera_add(location=location)
    camera = bpy.context.active_object

    # Add track-to constraint
    constraint = camera.constraints.new(type='TRACK_TO')

    # Create empty at target for tracking
    bpy.ops.object.empty_add(location=target)
    target_empty = bpy.context.active_object
    target_empty.name = "CameraTarget"

    constraint.target = target_empty
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'

    # Set as active camera
    bpy.context.scene.camera = camera

    return camera


def setup_lighting():
    """Set up basic three-point lighting."""
    # Remove default light
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.select_by_type(type='LIGHT')
    bpy.ops.object.delete()

    # Key light
    bpy.ops.object.light_add(type='AREA', location=(5, -5, 5))
    key_light = bpy.context.active_object
    key_light.name = "KeyLight"
    key_light.data.energy = 500
    key_light.data.size = 5

    # Fill light
    bpy.ops.object.light_add(type='AREA', location=(-5, -3, 3))
    fill_light = bpy.context.active_object
    fill_light.name = "FillLight"
    fill_light.data.energy = 200
    fill_light.data.size = 5

    # Rim light
    bpy.ops.object.light_add(type='AREA', location=(0, 5, 3))
    rim_light = bpy.context.active_object
    rim_light.name = "RimLight"
    rim_light.data.energy = 300
    rim_light.data.size = 3


def main():
    """Main setup function."""
    print("Setting up Demo Movie scene...")

    # Clear existing scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Create animated objects
    create_animated_cube(name="MainCube", location=(0, 0, 1))

    # Setup camera
    setup_camera()

    # Setup lighting
    setup_lighting()

    # Set render settings
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 120
    scene.render.fps = 24

    print("Demo Movie scene setup complete!")


if __name__ == "__main__":
    main()
