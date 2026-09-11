#!/usr/bin/env python3
"""
Arc study for the fruit_bowl scene, rendered on Modal cloud GPUs.

Three arcs, each 24 frames stitched into a 1-second GIF at 24 fps:
    arc_x.gif   — POINT light sweeps a hemispheric arc in the XZ plane
    arc_y.gif   — POINT light sweeps a hemispheric arc in the YZ plane
    arc_cam.gif — CAMERA orbits horizontally around the bowl (full 360°)
                  with a fixed overhead light. Camera is elevated above
                  the floor plane and tracks the bowl center.

All pre-existing lights are removed before rendering.

Usage:
    python scripts/demos/lighting/light_arc_modal.py
"""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "marionette" / "src"))

from marionette.modal_render import app, render_single_frame, upload_to_volume
from marionette.rigs import ArcRig, SceneBounds, lights_setup_script, orbit_positions


BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
BLEND_FILE = "/Users/sanjeev/Documents/blenderclass/character_modeling/fruit_bowl.blend"
OUTPUT_DIR = "/Users/sanjeev/Documents/3d/renders/fruit_bowl_light_arc"
VOLUME_PATH = "models/scenes/fruit_bowl.blend"

NUM_FRAMES = 24
FPS = 24
RADIUS_MULTIPLIER = 2.0      # radius = subject_max_extent * this
BACKDROP_SKIP_DIM = 20.0     # meshes with any dim above this are treated as backdrops
LIGHT_ENERGY = 3000.0        # watts for POINT light
RESOLUTION = 1024
SAMPLES = 64


def measure_bounds() -> SceneBounds:
    """Compute the subject's bounds once, locally, by opening the blend headlessly.

    Doing this here rather than inside every render container means the setup
    scripts we ship carry concrete numbers instead of duplicated rig math.
    """
    expr = f"""
import bpy, mathutils, json
pts = []
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    corners = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
    size = max(
        max(v.x for v in corners) - min(v.x for v in corners),
        max(v.y for v in corners) - min(v.y for v in corners),
        max(v.z for v in corners) - min(v.z for v in corners),
    )
    if size > {BACKDROP_SKIP_DIM}:
        continue
    pts.extend((v.x, v.y, v.z) for v in corners)
print('BOUNDS_JSON' + json.dumps(pts))
"""
    out = subprocess.run(
        [BLENDER, "--background", BLEND_FILE, "--python-expr", expr],
        capture_output=True, text=True,
    ).stdout
    line = next(l for l in out.splitlines() if l.startswith("BOUNDS_JSON"))
    import json
    return SceneBounds.from_points(json.loads(line[len("BOUNDS_JSON"):]))


def build_setup_script(bounds: SceneBounds, axis: str, frame_i: int) -> str:
    """Blender-Python run inside the render container before the frame is drawn.

    The rig computes light placement locally (see marionette.rigs.ArcRig); this
    emits only the resulting data plus camera framing.
    """
    rig = ArcRig(
        axis="fixed" if axis == "cam" else axis,
        num_frames=NUM_FRAMES,
        energy=LIGHT_ENERGY,
        radius_multiplier=RADIUS_MULTIPLIER,
    )
    config = rig.plan(bounds)[0].model_copy(
        update={"location": rig.position_at(bounds, frame_i)}
    )
    parts = [lights_setup_script([config], clear=True)]

    if axis == "cam":
        cam_loc = orbit_positions(
            bounds, NUM_FRAMES, radius_multiplier=RADIUS_MULTIPLIER * 1.2
        )[frame_i]
        parts.append(f"""
import mathutils
for _o in list(bpy.data.objects):
    if _o.type == 'CAMERA':
        bpy.data.objects.remove(_o, do_unlink=True)
_cd = bpy.data.cameras.new('OrbitCam')
_co = bpy.data.objects.new('OrbitCam', _cd)
bpy.context.collection.objects.link(_co)
_co.location = {cam_loc!r}
_d = mathutils.Vector({bounds.center!r}) - mathutils.Vector({cam_loc!r})
_co.rotation_euler = _d.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = _co
""".strip())
    else:
        parts.append(f"""
import mathutils
if bpy.context.scene.camera is None:
    _cams = [o for o in bpy.data.objects if o.type == 'CAMERA']
    if _cams:
        bpy.context.scene.camera = _cams[0]
    else:
        _cd = bpy.data.cameras.new('AutoCam')
        _co = bpy.data.objects.new('AutoCam', _cd)
        bpy.context.collection.objects.link(_co)
        _R = {bounds.radius!r}
        _c = mathutils.Vector({bounds.center!r})
        _co.location = (_c.x + _R*2.4, _c.y - _R*2.4, _c.z + _R*1.2)
        _co.rotation_euler = (_c - _co.location).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.scene.camera = _co
""".strip())

    parts.append(
        f"bpy.context.scene.render.resolution_x = {RESOLUTION}\n"
        f"bpy.context.scene.render.resolution_y = {RESOLUTION}"
    )
    return "\n\n".join(parts)


def build_render_tasks(bounds: SceneBounds):
    """Return (tasks, meta): tasks for starmap, meta[job_id-1] = (axis, frame_i)."""
    tasks = []
    meta = []
    for axis in ('x', 'y', 'cam'):
        for i in range(NUM_FRAMES):
            job_id = len(tasks) + 1
            cfg = {
                "engine": "CYCLES",
                "samples": SAMPLES,
                "device": "GPU",
                "denoising": True,
                "setup_script": build_setup_script(bounds, axis, i),
            }
            tasks.append((
                job_id,
                VOLUME_PATH,
                f"arc_{axis}_{i:03d}.png",
                cfg,
            ))
            meta.append((axis, i))
    return tasks, meta


def stitch_gif(input_dir: Path, pattern: str, output_gif: Path, fps: int):
    """One-pass ffmpeg GIF with palettegen for good color."""
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(input_dir / pattern),
        "-vf",
        f"fps={fps},scale=800:-1:flags=lanczos,"
        f"split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        str(output_gif),
    ]
    print(f"  ffmpeg → {output_gif.name}")
    subprocess.run(cmd, check=True, capture_output=True)


def main():
    blend_path = Path(BLEND_FILE)
    if not blend_path.exists():
        print(f"Error: blend file not found: {BLEND_FILE}")
        sys.exit(1)

    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Uploading {blend_path.name} → volume:{VOLUME_PATH}")
    upload_to_volume(str(blend_path), VOLUME_PATH, force=True)

    print("Measuring subject bounds locally...")
    bounds = measure_bounds()
    print(f"  center={tuple(round(c,3) for c in bounds.center)} extent={bounds.extent:.3f}")

    tasks, meta = build_render_tasks(bounds)
    print(f"\nRendering {len(tasks)} frames on Modal "
          f"({NUM_FRAMES} per arc × 3 arcs) — {RESOLUTION}x{RESOLUTION}, "
          f"CYCLES, {SAMPLES} samples, A10G GPU")

    start = time.time()
    with app.run():
        results = list(render_single_frame.starmap(tasks))
    print(f"\nRender wall time: {time.time() - start:.1f}s")

    # Save PNGs locally, indexed via meta
    successes = {'x': 0, 'y': 0, 'cam': 0}
    for r in results:
        job_id = r.get("frame_number")
        if not job_id:
            continue
        axis, i = meta[job_id - 1]
        if r.get("success") and r.get("output_data"):
            out_file = output_path / f"arc_{axis}_{i:03d}.png"
            with open(out_file, "wb") as f:
                f.write(r["output_data"])
            successes[axis] += 1
        else:
            print(f"  FAILED arc_{axis}_{i:03d}: {r.get('error', 'unknown')}")

    print(f"\nSaved: x={successes['x']}/{NUM_FRAMES}, "
          f"y={successes['y']}/{NUM_FRAMES}, "
          f"cam={successes['cam']}/{NUM_FRAMES}")

    # Stitch a GIF per arc
    print("\nStitching GIFs...")
    for axis in ('x', 'y', 'cam'):
        if successes[axis] == NUM_FRAMES:
            stitch_gif(output_path, f"arc_{axis}_%03d.png",
                       output_path / f"arc_{axis}.gif", FPS)
        else:
            print(f"  skipping arc_{axis}.gif (only {successes[axis]}/{NUM_FRAMES} frames)")

    print(f"\nDone. Output: {output_path}")


if __name__ == "__main__":
    main()
