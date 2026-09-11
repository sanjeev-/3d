"""CelLook against a real Blender: graph realization and a render assertion.

The render test is the one that matters. A cel shader's defining property is
that lighting is *quantized* — a sphere should resolve to a couple of flat
colors, not a smooth gradient. That is behavioral, not structural, so it is
checked by rendering and counting distinct luminances.
"""

from collections import Counter
from collections import Counter
from pathlib import Path

import pytest

bpy = pytest.importorskip("bpy")

from marionette.looks import CelLook, CelParams, LookPipeline
from marionette.looks.cel import _warm_shadow
from marionette.shading import MaterialRole, RoleMap, Selector
from marionette.shading.graph import OWNER_PROP


@pytest.fixture
def sphere_scene():
    """An empty scene with one smooth-shaded sphere named 'body' and a camera."""
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene

    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
    sphere = bpy.context.active_object
    sphere.name = "body"
    for poly in sphere.data.polygons:
        poly.use_smooth = True
    material = bpy.data.materials.new("body_mat")
    material.use_nodes = True
    sphere.data.materials.append(material)

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.0, -5.0, 0.0)
    cam.rotation_euler = (1.5707963, 0.0, 0.0)
    scene.camera = cam

    scene.render.resolution_x = 96
    scene.render.resolution_y = 96
    scene.render.film_transparent = True
    return scene


def _roles():
    return RoleMap({MaterialRole.SKIN: Selector(names=("body",))})


def _render_colors(scene, tmp_path, name="cel") -> list:
    """Render and return the linear RGB of every opaque pixel.

    Three settings matter for measuring a *quantized* image, and all three were
    wrong-by-default before this was calibrated:

    * ``use_denoising`` must be off. The denoiser smooths flat regions, which
      is precisely the property under test — it turned 2 exact colors into 350.
    * ``filter_width`` is minimized so the reconstruction filter does not blend
      neighbours across the terminator.
    * OpenEXR, not PNG. 8-bit quantization splits each flat band across
      adjacent codes and inflates any distinct-value count.
    """
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.filter_width = 0.01
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "RGBA"
    out = Path(tmp_path) / f"{name}.exr"
    scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)

    image = bpy.data.images.load(str(out))
    px = list(image.pixels)
    colors = [
        tuple(px[i : i + 3]) for i in range(0, len(px), 4) if px[i + 3] > 0.999
    ]
    bpy.data.images.remove(image)
    return colors


def _bands(colors, places=2):
    """Distinct colors and their pixel counts, most common first."""
    return Counter(tuple(round(c, places) for c in col) for col in colors).most_common()


#: A light perpendicular to the view, so the terminator crosses the sphere
#: near its centre and both bands cover roughly half the surface.
SIDE_LIT = CelParams(light_direction=(0.0, 90.0, 0.0))
NO_RIM = SIDE_LIT.model_copy(update={"rim_size": -1.0})


class TestGraphRealization:
    def test_builds_onto_a_real_material(self, sphere_scene):
        material = bpy.data.materials["body_mat"]
        CelLook().apply_to_material(material)

        types = {n.bl_idname for n in material.node_tree.nodes}
        assert "ShaderNodeEmission" in types
        assert "ShaderNodeBsdfPrincipled" not in types
        assert material.use_backface_culling is True

    def test_rebuilding_is_idempotent(self, sphere_scene):
        material = bpy.data.materials["body_mat"]
        look = CelLook()
        look.apply_to_material(material)
        first = len(material.node_tree.nodes)
        look.apply_to_material(material)
        look.apply_to_material(material)
        assert len(material.node_tree.nodes) == first

    def test_owned_nodes_are_tagged(self, sphere_scene):
        material = bpy.data.materials["body_mat"]
        CelLook().apply_to_material(material)
        owned = [n for n in material.node_tree.nodes if n.get(OWNER_PROP) == "marionette.cel"]
        assert len(owned) >= 10

    def test_smooth_variant_builds_too(self, sphere_scene):
        material = bpy.data.materials["body_mat"]
        CelLook(CelParams(shadow_smoothness=0.3)).apply_to_material(material)
        assert any(n.bl_idname == "ShaderNodeMapRange" for n in material.node_tree.nodes)


class TestPipeline:
    def test_full_pipeline_runs(self, sphere_scene):
        result = LookPipeline(CelLook(), roles=_roles()).apply(sphere_scene)
        assert result.warnings == []
        assert result.context.objects_for(MaterialRole.SKIN) == ["body"]
        assert sphere_scene.view_settings.view_transform == "Standard"

    def test_direction_proxy_sun_is_created_with_zero_energy(self, sphere_scene):
        LookPipeline(CelLook(), roles=_roles()).apply(sphere_scene)
        suns = [o for o in bpy.data.objects if o.type == "LIGHT"]
        assert len(suns) == 1
        assert suns[0].data.type == "SUN"
        assert suns[0].data.energy == 0.0

    def test_outlines_are_off_by_default(self, sphere_scene):
        result = LookPipeline(CelLook(), roles=_roles()).apply(sphere_scene)
        assert result.context.data["outlines"] == 0

    def test_outline_adds_an_inverted_solidify(self, sphere_scene):
        result = LookPipeline(CelLook(outline_thickness=0.02), roles=_roles()).apply(sphere_scene)
        assert result.context.data["outlines"] == 1
        mod = bpy.data.objects["body"].modifiers["Marionette_Outline"]
        assert mod.type == "SOLIDIFY"
        assert mod.use_flip_normals is True
        assert mod.thickness == pytest.approx(0.02)

    def test_outline_is_not_duplicated_on_reapply(self, sphere_scene):
        look = CelLook(outline_thickness=0.02)
        LookPipeline(look, roles=_roles()).apply(sphere_scene)
        LookPipeline(look, roles=_roles()).apply(sphere_scene)
        mods = [m for m in bpy.data.objects["body"].modifiers if m.name.startswith("Marionette")]
        assert len(mods) == 1

    def test_the_look_fixes_a_wrong_view_transform_itself(self, sphere_scene):
        sphere_scene.view_settings.view_transform = "AgX"
        LookPipeline(CelLook(), roles=_roles()).apply(sphere_scene, strict=True)
        assert sphere_scene.view_settings.view_transform == "Standard"

    def test_skipping_configure_render_is_caught_as_a_postcondition(self, sphere_scene):
        from marionette.looks import LookValidationError

        # The dangerous case: AgX would render a plausible but wrong image.
        sphere_scene.view_settings.view_transform = "AgX"
        pipeline = LookPipeline(CelLook(), roles=_roles(), skip=("configure_render",))
        with pytest.raises(LookValidationError, match="did not reach its required state"):
            pipeline.apply(sphere_scene, strict=True)

    def test_postcondition_failure_is_a_warning_when_not_strict(self, sphere_scene):
        sphere_scene.view_settings.view_transform = "AgX"
        result = LookPipeline(
            CelLook(), roles=_roles(), skip=("configure_render",)
        ).apply(sphere_scene, strict=False)
        assert any("view transform" in w for w in result.warnings)


class TestRenderedOutput:
    """The behavioral checks: does it actually look cel-shaded?"""

    def test_sphere_renders_as_exactly_two_flat_colors(self, sphere_scene, tmp_path):
        LookPipeline(CelLook(NO_RIM), roles=_roles()).apply(sphere_scene)
        bands = _bands(_render_colors(sphere_scene, tmp_path))

        assert len(bands) == 2, bands[:6]
        total = sum(n for _, n in bands)
        assert total > 500, "sphere should cover a good part of the frame"
        # A side light splits the visible hemisphere down the middle.
        for _, count in bands:
            assert 0.4 < count / total < 0.6, bands

    def test_the_two_colors_are_the_configured_base_and_shadow(self, sphere_scene, tmp_path):
        LookPipeline(CelLook(NO_RIM), roles=_roles()).apply(sphere_scene)
        bands = _bands(_render_colors(sphere_scene, tmp_path))
        rendered = {c for c, _ in bands}

        expected_base = tuple(round(c, 2) for c in (0.8, 0.8, 0.8))
        expected_shadow = tuple(round(c, 2) for c in _warm_shadow((0.8, 0.8, 0.8, 1.0))[:3])
        assert rendered == {expected_base, expected_shadow}, (rendered, expected_shadow)

    def test_shadow_is_a_hue_shift_not_a_neutral_darkening(self, sphere_scene, tmp_path):
        """The single most important cel decision, asserted on real pixels."""
        LookPipeline(CelLook(NO_RIM), roles=_roles()).apply(sphere_scene)
        bands = _bands(_render_colors(sphere_scene, tmp_path))

        lit, shadow = sorted((c for c, _ in bands), key=sum, reverse=True)
        assert shadow[0] > shadow[1], f"shadow should be warm (r>g): {shadow}"
        assert shadow[0] - shadow[2] > shadow[1] - shadow[2], f"not a hue shift: {shadow}"
        # A neutral darkening would keep all three ratios equal.
        ratios = [shadow[i] / lit[i] for i in range(3)]
        assert max(ratios) - min(ratios) > 0.05, ratios

    def test_rim_adds_two_more_flat_values(self, sphere_scene, tmp_path):
        LookPipeline(CelLook(SIDE_LIT), roles=_roles()).apply(sphere_scene)
        bands = _bands(_render_colors(sphere_scene, tmp_path))
        # Two shading bands, each with and without the rim contribution.
        assert len(bands) == 4, bands
        assert sum(n for _, n in bands[:2]) / sum(n for _, n in bands) > 0.9

    def test_smooth_variant_is_not_quantized(self, sphere_scene, tmp_path):
        # The control: same scene and light, only shadow_smoothness differs.
        # Proves the assertions above measure quantization, not the scene.
        smooth = NO_RIM.model_copy(update={"shadow_smoothness": 0.9})
        LookPipeline(CelLook(smooth), roles=_roles()).apply(sphere_scene)
        smooth_bands = len(_bands(_render_colors(sphere_scene, tmp_path, "smooth")))

        LookPipeline(CelLook(NO_RIM), roles=_roles()).apply(sphere_scene)
        hard_bands = len(_bands(_render_colors(sphere_scene, tmp_path, "hard")))

        assert hard_bands == 2
        assert smooth_bands > 20, f"smooth={smooth_bands} hard={hard_bands}"
