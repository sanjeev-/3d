import os
import math
from marionette.scene import Scene
from marionette.camera import CameraConfig, DOFConfig
from marionette.configs import CharacterConfig
from marionette.render import Renderer, RenderConfig, RenderEngine, FileFormat
from marionette.types import Interpolation

# --- CONFIGURATION ---
SCENE_FILE = "/Users/sanjeev/Documents/3d/shared/assets/models/scenes/modern-dark-bedroom_4998bbdf-bd20-48ff-8236-25186413783f.blend"
CHARACTER_FILE = "/Users/sanjeev/Documents/3d/shared/assets/models/characters/body_mesh_male.blend"
OUTPUT_DIR = "renders/rack_focus_demo"

def setup_rack_focus_scene():
    # 1. Initialize Scene (120 frames to allow for padding)
    scene = Scene(SCENE_FILE)
    scene.set_timeline(start=1, end=120, fps=24)
    
    # 2. Add "Close" Character (Near the camera)
    char_close_cfg = CharacterConfig(
        name="Char_Close",
        blend_file=CHARACTER_FILE,
        object_name="body_mesh_male",
        location=(9.0, -5.0, 0),
        rotation=(0, 0, 265), # Facing away from camera
    )
    char_close = scene.add_character(char_close_cfg)
    
    # 3. Add "Far" Character (Down the x-axis)
    char_far_cfg = CharacterConfig(
        name="Char_Far",
        blend_file=CHARACTER_FILE,
        object_name="body_mesh_male",
        location=(4.0, -4.8, 0),
        rotation=(0, 0, 85), # Facing toward camera
    )
    char_far = scene.add_character(char_far_cfg)
    
    # 4. Create Camera with shallow Depth of Field
    # fstop=1.4 or 1.8 creates a very blurry background/foreground
    cam_config = CameraConfig(
        name="RackFocusCamera",
        location=(10.5, -5.2, 1.6), 
        rotation=(90, 0, 95),
        lens=50.0, # 50mm or 85mm are best for rack focus
        dof=DOFConfig(enabled=True, fstop=1.8) 
    )
    camera = scene.add_camera(cam_config)
    
    # 5. Animate the Rack Focus
    # Duration: 3 seconds * 24 fps = 72 frames
    start_frame = 20
    end_frame = start_frame + 72 # Frame 92
    
    # Frame 1 to 20: Stay focused on the Far person
    camera.focus_on(char_far, frame=1)
    camera.focus_on(char_far, frame=start_frame)
    
    # Rack focus to the Close person over 72 frames
    camera.focus_on(char_close, frame=end_frame, interpolation=Interpolation.BEZIER)
    
    # Hold focus on Close person until the end
    camera.focus_on(char_close, frame=120)

    # 6. Setup Renderer
    renderer = Renderer(scene)
    render_config = RenderConfig(
        output_dir=OUTPUT_DIR,
        engine=RenderEngine.CYCLES,
        samples=128,
        resolution=(1280, 720),
        file_format=FileFormat.PNG,
        use_gpu=True
    )
    renderer.apply_config(render_config)
    
    print(f"Rack Focus distances:")
    print(f" - Far Person: {camera.get_distance_to(char_far):.2f}m")
    print(f" - Close Person: {camera.get_distance_to(char_close):.2f}m")
    
    print(f"Starting render sequence...")
    renderer.render_sequence(start=1, end=120)

if __name__ == "__main__":
    try:
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        setup_rack_focus_scene()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()