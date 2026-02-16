import math
import os
from marionette.scene import Scene
from marionette.camera import CameraConfig, CameraType
from marionette.render import Renderer, RenderConfig, RenderEngine

# --- PATHS ---
FILE_PATH = "/Users/sanjeev/Documents/3d/shared/assets/models/scenes/modern-dark-bedroom_4998bbdf-bd20-48ff-8236-25186413783f.blend"
OUTPUT_DIR = "renders/rotation_study"

def rotation_study():
    scene = Scene(FILE_PATH)

    # Initial Camera Setup
    cam_blueprint = CameraConfig(
        name="RotationStudyCam",
        type=CameraType.PERSP,
        location=(5, -5.0, 0.98866),
        rotation=(math.radians(90), math.radians(0), math.radians(0)),
        lens=70.0
    )

    # Add camera to scene
    cam = scene.add_camera(cam_blueprint)

    render_blueprint = RenderConfig(
        output_dir=OUTPUT_DIR,
        engine=RenderEngine.CYCLES,
        samples=64,
        resolution=(1024, 1024),
        filename_pattern="z_rot_{frame:04d}"
    )

    renderer = Renderer(scene)
    renderer.apply_config(render_blueprint)

    print(f"📸 Starting Z-Rotation Study...")
    
    # Iterate through Z rotation angles in degrees
    for idx, z_deg in enumerate(range(0, 360, 30)):
        # Update the rotation: 
        # Keep X at 90 (looking forward), Y at 0, and update Z
        cam.rotation = (math.radians(90), 0, math.radians(z_deg))
        
        # Format filename to include the degree
        filename = f"render_z_rot_{z_deg:03d}"
        
        print(f"Rendering: {filename} at {z_deg}°...")
        
        renderer.render_frame(idx+1)

    print(f"🏁 Study complete. Images saved to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    try:
        rotation_study()
    except Exception as e:
        print(f"ERROR: {e}")