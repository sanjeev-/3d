import os
import math
from marionette.scene import Scene
from marionette.camera import CameraConfig
from marionette.configs import CharacterConfig
from marionette.render import Renderer, RenderConfig, RenderEngine, FileFormat
from marionette.types import Interpolation
from marionette.movement import GenericCameraMovement, Waypoint

# --- CONFIGURATION ---
SCENE_FILE = "/Users/sanjeev/Documents/3d/shared/assets/models/scenes/hidden_alley/ph_hidden_alley.blend"
CHARACTER_FILE = "/Users/sanjeev/Documents/3d/shared/assets/models/characters/body_mesh_male.blend"
OUTPUT_DIR = "renders/crane_shot_alley"

def setup_and_render():
    # 1. Load scene
    scene = Scene(SCENE_FILE)
    scene.set_timeline(start=1, end=200, fps=24)
    
    # 2. Load character
    # Positioned at (0.78, 11.9, 0). Rotation -180 typically faces "forward" in Blender.
    char_name = "body_mesh_male"
    character_config = CharacterConfig(
        name="female_v006lowresUV",
        blend_file=CHARACTER_FILE,
        object_name=char_name,
        location=(0.78, 11.9, 0),
        rotation=(0, 0, -180),
    )
    character = scene.add_character(character_config)
    
    # 3. Create camera
    # We place the camera in front of the character (approx 3 meters away on Y)
    # Start: Eye level (~1.6m)
    start_loc = (0.78, 8.9, 1.6) 
    cam_config = CameraConfig(
        name="CraneCamera",
        location=start_loc,
        rotation=(0, 0, 0), # Rotation will be controlled by 'look_at'
        lens=35.0, # Slightly wider for a cinematic crane feel
    )
    camera = scene.add_camera(cam_config)
    
    # 4. Define Crane Movement using Waypoints
    # We move the camera UP 5 meters (1.6 -> 6.6) 
    # and BACK 2 meters (8.9 -> 6.9) to create the crane arc.
    end_loc = (0.78, 6.9, 6.6)
    
    waypoints = [
        Waypoint(
            frame=1,
            location=start_loc,
            look_at=char_name # Tracks the character's mesh
        ),
        Waypoint(
            frame=200,
            location=end_loc,
            look_at=char_name
        )
    ]
    
    # Apply the movement logic (uses BEZIER interpolation for smooth acceleration/deceleration)
    crane_move = GenericCameraMovement(waypoints=waypoints, interpolation=Interpolation.BEZIER)
    crane_move.apply(camera)
    
    # 5. Setup renderer
    renderer = Renderer(scene)
    render_config = RenderConfig(
        output_dir=OUTPUT_DIR,
        engine=RenderEngine.CYCLES,
        samples=64,
        resolution=(960, 540),
        file_format=FileFormat.PNG,
        use_gpu=True,
        transparent_bg=False
    )
    renderer.apply_config(render_config)
    
    print(f"Starting crane shot render (200 frames)...")
    renderer.render_sequence(start=1, end=200)
    print(f"Render complete! Files saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    try:
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        setup_and_render()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()