"""Golden-image harness: render a fixed scene per look and compare to a reference.

Unit tests verify that a graph is *built*; they cannot tell you the look
*changed*. Swap two constants in ``_warm_shadow`` and every structural
assertion still passes while every cel material in the project shifts hue.
Shared node groups sit under many looks, so that class of regression is the one
most likely to escape — this is the cheap answer to "did I break the look?".

Three render settings are wrong by default for this purpose, and all three were
found the hard way while calibrating the CelLook render tests:

* ``use_denoising`` smooths flat regions — it turned 2 exact colors into 350.
* the default 1.5px reconstruction filter blends neighbours across the
  terminator, so flat bands acquire hundreds of intermediate values.
* 8-bit PNG splits each flat band across adjacent codes.

So: denoise off, minimal filter, float EXR. A fixed seed and disabled adaptive
sampling keep repeat runs identical.
"""

from pathlib import Path
from typing import NamedTuple

import bpy
import mathutils

from marionette.rigs import orbit_positions, SceneBounds

#: Where reference renders live.
GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"

#: Small enough to stay fast and cheap to commit; large enough that a hue shift
#: or a moved terminator is unmissable.
RESOLUTION = 96

#: Views around the subject. A single view cannot see a view-dependent term
#: like the rim light going wrong on the far side.
VIEWS = 3


def build_scene():
    """Construct the reference scene. Must be byte-identical every run.

    Three primitives cover the cases that break shading differently: a sphere
    (smooth curvature), a torus (curvature plus a silhouette hole), and a cube
    (hard edges and flat faces). They are named to match
    ``anime_character_roles`` so looks bind to them without special casing.
    """
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene

    specs = [
        ("body", (-2.2, 0.0, 0.0), (0.80, 0.62, 0.52)),
        ("hair", (0.0, 0.0, 0.0), (0.30, 0.22, 0.18)),
        ("cloth", (2.2, 0.0, 0.0), (0.25, 0.35, 0.55)),
    ]

    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24, location=specs[0][1])
    bpy.context.active_object.name = "body"
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.9, minor_radius=0.32, major_segments=48, minor_segments=16,
        location=specs[1][1],
    )
    bpy.context.active_object.name = "hair"
    bpy.ops.mesh.primitive_cube_add(size=1.5, location=specs[2][1])
    bpy.context.active_object.name = "cloth"

    for name, _loc, color in specs:
        obj = bpy.data.objects[name]
        if name != "cloth":  # leave the cube faceted on purpose
            for poly in obj.data.polygons:
                poly.use_smooth = True
        material = bpy.data.materials.new(f"{name}_mat")
        material.use_nodes = True
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is not None:
            principled.inputs["Base Color"].default_value = (*color, 1.0)
        obj.data.materials.append(material)

    cam_data = bpy.data.cameras.new("GoldenCam")
    cam_data.lens = 50.0
    camera = bpy.data.objects.new("GoldenCam", cam_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    scene.render.resolution_x = RESOLUTION
    scene.render.resolution_y = RESOLUTION
    scene.render.film_transparent = True
    return scene


def _place_camera(scene, view_index: int):
    """Move the camera to one station of a fixed turntable, aimed at the origin."""
    bounds = SceneBounds(center=(0.0, 0.0, 0.0), extent=7.0)
    position = orbit_positions(bounds, VIEWS, radius_multiplier=2.6, elevation_ratio=0.5)[
        view_index
    ]
    camera = scene.camera
    camera.location = position
    direction = mathutils.Vector((0.0, 0.0, 0.0)) - mathutils.Vector(position)
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()


def render_view(scene, view_index: int, out_path: Path, samples: int = 1):
    """Render one turntable view with deterministic, quantization-safe settings.

    These are applied *after* the look has configured the scene, so every look
    is measured through the same instrument.
    """
    _place_camera(scene, view_index)

    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.seed = 0
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.filter_width = 0.01
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.exr_codec = "ZIP"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)
    return out_path


def load_pixels(path: Path):
    """Read an EXR into a flat list of floats, then drop the datablock."""
    image = bpy.data.images.load(str(path))
    try:
        return list(image.pixels)
    finally:
        bpy.data.images.remove(image)


#: A per-channel difference below this is treated as noise, not a change.
CHANNEL_EPSILON = 0.01


class Diff(NamedTuple):
    """Result of comparing two renders."""

    mean_abs: float
    max_abs: float
    changed_fraction: float

    def __str__(self):
        return (
            f"changed {self.changed_fraction:.2%} of pixels "
            f"(mean {self.mean_abs:.5f}, max {self.max_abs:.5f})"
        )


def compare(rendered, golden, channel_epsilon: float = CHANNEL_EPSILON) -> Diff:
    """Compare two pixel buffers on RGB only.

    ``changed_fraction`` is the headline number, not the mean. Mean absolute
    error is badly insensitive to *localized* changes: moving a cel terminator
    repaints only a thin band, so a clearly-wrong image can sit at a mean of
    0.002 — indistinguishable from noise. Counting pixels that moved by more
    than a visible amount catches that, and stays near zero for a look that
    genuinely did not change.

    Alpha is excluded deliberately: it is coverage, not look, and a change to
    it surfaces in RGB anyway through the premultiplied result.
    """
    if len(rendered) != len(golden):
        raise ValueError(
            f"buffer size mismatch: rendered {len(rendered)} vs golden {len(golden)}; "
            "the reference was captured at a different resolution"
        )

    total = 0.0
    worst = 0.0
    channels = 0
    changed = 0
    pixels = 0

    for i in range(0, len(rendered), 4):
        pixel_worst = 0.0
        for channel in range(3):
            delta = abs(rendered[i + channel] - golden[i + channel])
            total += delta
            pixel_worst = max(pixel_worst, delta)
            channels += 1
        worst = max(worst, pixel_worst)
        pixels += 1
        if pixel_worst > channel_epsilon:
            changed += 1

    return Diff(
        mean_abs=total / channels if channels else 0.0,
        max_abs=worst,
        changed_fraction=changed / pixels if pixels else 0.0,
    )


def golden_path(case_name: str, view_index: int) -> Path:
    return GOLDEN_DIR / f"{case_name}_{view_index:02d}.exr"
