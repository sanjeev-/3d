import os
from marionette.scene import Scene
from marionette.camera import CameraConfig
from marionette.render import Renderer, RenderConfig, RenderEngine, FileFormat
from marionette.camera_movements import DollyMovement, GenericCameraMovement, Waypoint
from marionette.types import Interpolation
from marionette.configs import HDRIConfig

# --- CONFIGURATION ---
BLEND_FILE = "/Users/sanjeev/Documents/3d/shared/assets/models/scenes/modern-dark-bedroom_4998bbdf-bd20-48ff-8236-25186413783f.blend"
OUTPUT_DIR = "renders/dolly_in_monster_pan_hdri_1"
HDRI_FILE = "shared/assets/hdris/moonless_golf_4k.exr"

def run_cinematic_camera():
    scene = Scene(BLEND_FILE)
    scene.set_timeline(start=1, end=200, fps=24)
    scene.set_hdri(HDRIConfig(
        path=HDRI_FILE,
        strength=1.5,
    ))
    
    cam_config = CameraConfig(
        name="MainShot",
        location=(10, -6, 1),
        rotation=(90, 0, 90),
        lens=24.0,
    )
    cam = scene.add_camera(cam_config)

    dolly = DollyMovement(
        start_frame=1,
        end_frame=180,
        start_pos=(10, -6, 1),
        end_pos=(2, -6, 1),
        interpolation=Interpolation.LINEAR
    )
    scene.apply_movement(cam, dolly)

    path = GenericCameraMovement([
        Waypoint(
            frame=181, 
            location=(2, -6, 1), 
        ),
        Waypoint(
            frame=200, 
            location=(2, -6, 1), 
            look_at="Monster",
            lens=50.0
        ),
    ], interpolation=Interpolation.LINEAR)
    
    scene.apply_movement(cam, path)

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

    print(f"Starting render sequence...")
    renderer.render_sequence(start=1, end=200)
    print(f"Render complete! Files saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    try:
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        run_cinematic_camera()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")