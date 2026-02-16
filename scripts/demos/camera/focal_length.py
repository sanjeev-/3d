import math
import os
from marionette.scene import Scene
from marionette.camera import CameraConfig, CameraType
from marionette.render import Renderer, RenderConfig, RenderEngine

# --- PATHS ---
FILE_PATH = "/Users/sanjeev/Documents/3d/shared/assets/models/scenes/modern-dark-bedroom_4998bbdf-bd20-48ff-8236-25186413783f.blend"
OUTPUT_DIR = "renders/focal_length"

def focal_length_study():
    scene = Scene(FILE_PATH)

    cam_blueprint = CameraConfig(
        name="LensStudyCam",
        type=CameraType.PERSP,
        location=(11.281, -6.0, 0.98866),
        rotation=(math.radians(90), math.radians(0), math.radians(90)),
        lens=10.0
    )

    # Add camera to scene
    cam = scene.add_camera(cam_blueprint)

    # 3. Setup Renderer Blueprint
    render_blueprint = RenderConfig(
        output_dir=OUTPUT_DIR,
        engine=RenderEngine.CYCLES,
        samples=64,
        resolution=(1024, 1024)
    )

    renderer = Renderer(scene)
    renderer.apply_config(render_blueprint)

    print(f"📸 Starting Focal Length Study...")
    
    for lens_val in range(10, 201, 10):
        cam.data.lens = lens_val
        filename = f"focal_length_{lens_val:03d}mm"
        
        print(f"Rendering: {filename}...")
        
        renderer.render_frame(1, filename=filename)

    print(f"🏁 Study complete. Images saved to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    try:
        focal_length_study()
    except Exception as e:
        print(f"ERROR: {e}")