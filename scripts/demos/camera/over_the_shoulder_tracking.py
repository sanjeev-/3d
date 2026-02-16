import os
from marionette.scene import Scene
from marionette.camera import CameraConfig
from marionette.configs import CharacterConfig
from marionette.render import Renderer, RenderConfig, RenderEngine, FileFormat
from marionette.types import Interpolation

# --- CONFIGURATION ---
SCENE_FILE = "/Users/sanjeev/Documents/3d/shared/assets/models/scenes/modern-dark-bedroom_4998bbdf-bd20-48ff-8236-25186413783f.blend"
CHARACTER_FILE = "/Users/sanjeev/Documents/3d/shared/assets/models/characters/body_mesh_male.blend"
OUTPUT_DIR = "renders/over_the_shoulder_tracking"

def setup_and_render():
    # Load scene
    scene = Scene(SCENE_FILE)
    scene.set_timeline(start=1, end=200, fps=24)
    
    # Load character from collection at starting position
    character_config = CharacterConfig(
        name="female_v006lowresUV",
        blend_file=CHARACTER_FILE,
        object_name="body_mesh_male",
        location=(9, -5, 0),
        rotation=(0, 0, 265),
    )
    character = scene.add_character(character_config)
    
    # Create camera at starting position
    cam_config = CameraConfig(
        name="MainCamera",
        location=(10, -5.2, 1.7),
        rotation=(90, 0, 90),
        lens=24.0,
    )
    camera = scene.add_camera(cam_config)
    
    # Animate character: start at (9, -5, 1), end at (1, -5, 1)
    character.location = (9, -5, 0)
    character.keyframe("location", frame=1, interpolation=Interpolation.LINEAR)
    
    character.location = (1, -5, 0)
    character.keyframe("location", frame=200, interpolation=Interpolation.LINEAR)
    
    # Animate camera: start at (10, -5.2, 1.7), end at (2, -5.2, 1.7)
    camera.location = (10, -5.2, 1.7)
    camera.keyframe("location", frame=1, interpolation=Interpolation.LINEAR)
    
    camera.location = (2, -5.2, 1.7)
    camera.keyframe("location", frame=200, interpolation=Interpolation.LINEAR)
    
    # Setup renderer
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
    
    print(f"Starting render sequence (200 frames at 24fps)...")
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