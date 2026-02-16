#!/usr/bin/env python3
"""
Focal Length Study — renders on Modal cloud GPUs.

Renders a bedroom scene at 20 different focal lengths (10mm-200mm)
using Modal's distributed GPU infrastructure. All frames render in
parallel and results are downloaded locally.

The .blend file is uploaded once to a Modal Volume so each worker
reads it from cloud storage instead of receiving 284 MB in its task
tuple (which caused OOM when multiplied across 20 workers).

Usage:
    python scripts/demos/camera/focal_length_modal.py
"""

import sys
import time
from pathlib import Path

# Add marionette to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "marionette" / "src"))

from marionette.modal_render import app, render_single_frame, upload_to_volume

# --- Configuration ---
BLEND_FILE = "/Users/sanjeev/Documents/3d/shared/assets/models/scenes/modern-dark-bedroom_4998bbdf-bd20-48ff-8236-25186413783f.blend"
OUTPUT_DIR = "/Users/sanjeev/Documents/3d/renders/focal_length"
LENS_VALUES = list(range(10, 201, 10))  # 10mm to 200mm in 10mm steps

# Camera setup
CAM_LOCATION = (11.281, -6.0, 0.98866)
CAM_ROTATION_DEG = (90, 0, 90)

# Volume path for the uploaded .blend
VOLUME_PATH = "models/scenes/modern-dark-bedroom.blend"


def build_setup_script(lens_val: int) -> str:
    """Build Blender Python setup for a specific focal length.

    This runs inside Blender on Modal before the frame is rendered.
    Now written as proper multi-line Python (rendered to a .py file).
    """
    return (
        f"import math\n"
        f"cam_data = bpy.data.cameras.new('LensStudyCam')\n"
        f"cam_obj = bpy.data.objects.new('LensStudyCam', cam_data)\n"
        f"bpy.context.collection.objects.link(cam_obj)\n"
        f"bpy.context.scene.camera = cam_obj\n"
        f"cam_obj.location = {CAM_LOCATION}\n"
        f"cam_obj.rotation_euler = ("
        f"math.radians({CAM_ROTATION_DEG[0]}), "
        f"math.radians({CAM_ROTATION_DEG[1]}), "
        f"math.radians({CAM_ROTATION_DEG[2]}))\n"
        f"cam_data.lens = {lens_val}\n"
        f"bpy.context.scene.render.resolution_x = 1024\n"
        f"bpy.context.scene.render.resolution_y = 1024"
    )


def main():
    blend_path = Path(BLEND_FILE)
    if not blend_path.exists():
        print(f"Error: Blend file not found: {BLEND_FILE}")
        sys.exit(1)

    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    # Upload .blend to Modal Volume once (not per-worker)
    print(f"Uploading blend file to Modal Volume: {blend_path.name}")
    upload_to_volume(str(blend_path), VOLUME_PATH, force=True)

    # Build render tasks — one per focal length, all run in parallel
    # Each task carries only a volume path string (~40 bytes), not file bytes (~284 MB)
    render_tasks = []
    for i, lens_val in enumerate(LENS_VALUES):
        config = {
            "engine": "CYCLES",
            "samples": 64,
            "device": "GPU",
            "denoising": True,
            "setup_script": build_setup_script(lens_val),
        }
        render_tasks.append((
            i + 1,                                    # frame number (job ID)
            VOLUME_PATH,                              # path on the volume
            f"focal_length_{lens_val:03d}mm.png",     # output filename
            config,                                   # render config
        ))

    print(f"\nStarting Focal Length Study on Modal")
    print(f"  {len(LENS_VALUES)} renders: {LENS_VALUES[0]}mm - {LENS_VALUES[-1]}mm")
    print(f"  GPU: A10G | Engine: CYCLES | Samples: 64 | Resolution: 1024x1024")
    print()

    start_time = time.time()

    # Launch all renders in parallel on Modal
    with app.run():
        results = list(render_single_frame.starmap(render_tasks))

    # Download results
    successful = 0
    failed = 0
    for result in results:
        frame_idx = result.get("frame_number", 1) - 1
        lens_val = LENS_VALUES[frame_idx] if 0 <= frame_idx < len(LENS_VALUES) else "?"

        if result.get("success") and result.get("output_data"):
            filename = f"focal_length_{lens_val:03d}mm.png"
            out_file = output_path / filename
            with open(out_file, "wb") as f:
                f.write(result["output_data"])
            size_kb = len(result["output_data"]) / 1024
            print(f"  saved {filename} ({size_kb:.0f} KB)")
            successful += 1
        else:
            print(f"  FAILED {lens_val}mm: {result.get('error', 'unknown')}")
            failed += 1

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.1f}s — {successful} rendered, {failed} failed")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()
