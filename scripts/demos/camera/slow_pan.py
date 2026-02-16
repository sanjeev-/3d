import math
import os
from marionette.scene import Scene
from marionette.camera import CameraConfig, CameraType
from marionette.render import Renderer, RenderConfig, RenderEngine
from marionette.types import Interpolation

# --- PATHS ---
FILE_PATH = "/Users/sanjeev/Documents/3d/shared/assets/models/scenes/modern-dark-bedroom_4998bbdf-bd20-48ff-8236-25186413783f.blend"
OUTPUT_DIR = "renders/slow_pan"

def slow_pan():
    scene = Scene(FILE_PATH)
    scene.set_timeline(start=1, end=120, fps=24)

    cam = scene.add_camera(CameraConfig(
        location=(0, -5, 1),
        rotation=(math.radians(90), 0, math.radians(90))
    ))

    cam.location = (12, -5, 1)
    cam.keyframe("location", frame=1, interpolation=Interpolation.LINEAR)

    cam.location = (0, -5, 1)
    cam.keyframe("location", frame=120, interpolation=Interpolation.LINEAR)

    # Render
    renderer = Renderer(scene)
    renderer.apply_config(RenderConfig(output_dir="renders/slow_pan"))
    renderer.render_sequence()

if __name__ == "__main__":
    try:
        slow_pan()
    except Exception as e:
        print(f"ERROR: {e}")