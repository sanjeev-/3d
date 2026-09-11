"""Light rig planning tests. Pure — the math runs without Blender."""

import math

import pytest

from marionette.configs import LightType
from marionette.rigs import (
    ArcRig,
    DirectionProxyRig,
    SceneBounds,
    ThreePointRig,
    lights_setup_script,
    orbit_positions,
)


class TestSceneBounds:
    def test_from_points(self):
        b = SceneBounds.from_points([(-1, -2, 0), (3, 2, 4)])
        assert b.center == (1.0, 0.0, 2.0)
        assert b.extent == 4.0
        assert b.radius == 2.0

    def test_empty_points_gives_unit_default(self):
        b = SceneBounds.from_points([])
        assert b.center == (0.0, 0.0, 0.0)
        assert b.extent == 1.0

    def test_radius_never_zero(self):
        # A degenerate (single-point) subject must not produce a zero radius,
        # which would collapse every rig onto the subject's origin.
        b = SceneBounds.from_points([(1, 1, 1)])
        assert b.radius > 0.0


class TestThreePointRig:
    def test_plans_three_lights_with_expected_ratios(self):
        b = SceneBounds(center=(0, 0, 0), extent=2.0)
        lights = ThreePointRig(key_energy=1000.0, fill_ratio=0.25, rim_ratio=0.5).plan(b)

        assert [l.name for l in lights] == ["Key", "Fill", "Rim"]
        assert lights[0].energy == 1000.0
        assert lights[1].energy == 250.0
        assert lights[2].energy == 500.0

    def test_lights_sit_at_the_requested_distance(self):
        b = SceneBounds(center=(5.0, 5.0, 0.0), extent=2.0)
        rig = ThreePointRig(distance_multiplier=3.0)
        for light in rig.plan(b):
            dx = light.location[0] - b.center[0]
            dy = light.location[1] - b.center[1]
            dz = light.location[2] - b.center[2]
            assert math.isclose(math.sqrt(dx * dx + dy * dy + dz * dz), b.radius * 3.0, rel_tol=1e-6)

    def test_scales_with_subject(self):
        small = ThreePointRig().plan(SceneBounds(extent=1.0))[0]
        large = ThreePointRig().plan(SceneBounds(extent=10.0))[0]
        assert abs(large.location[0]) > abs(small.location[0])


class TestArcRig:
    def test_sweeps_a_half_circle(self):
        b = SceneBounds(center=(0, 0, 0), extent=2.0)
        rig = ArcRig(axis="x", num_frames=3, radius_multiplier=1.0)

        first = rig.position_at(b, 0)
        middle = rig.position_at(b, 1)
        last = rig.position_at(b, 2)

        assert first == pytest.approx((1.0, 0.0, 0.0), abs=1e-9)
        assert middle == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)
        assert last == pytest.approx((-1.0, 0.0, 0.0), abs=1e-9)

    def test_y_axis_sweeps_the_other_plane(self):
        b = SceneBounds(extent=2.0)
        rig = ArcRig(axis="y", num_frames=3, radius_multiplier=1.0)
        assert rig.position_at(b, 0) == pytest.approx((0.0, 1.0, 0.0), abs=1e-9)

    def test_fixed_axis_parks_the_light_overhead(self):
        b = SceneBounds(center=(1, 2, 3), extent=2.0)
        assert ArcRig(axis="fixed", radius_multiplier=1.0).position_at(b, 7) == (1, 2, 4.0)

    def test_every_arc_position_keeps_the_radius(self):
        b = SceneBounds(extent=4.0)
        rig = ArcRig(axis="x", num_frames=12, radius_multiplier=2.0)
        for i in range(12):
            x, y, z = rig.position_at(b, i)
            assert math.isclose(math.sqrt(x * x + y * y + z * z), b.radius * 2.0, rel_tol=1e-9)

    def test_plan_frames_yields_one_config_per_frame(self):
        b = SceneBounds(extent=2.0)
        rig = ArcRig(num_frames=6)
        configs = rig.plan_frames(b)
        assert len(configs) == 6
        assert len({c.location for c in configs}) == 6

    def test_invalid_axis_rejected(self):
        with pytest.raises(ValueError, match="axis must be"):
            ArcRig(axis="z")


class TestDirectionProxyRig:
    def test_defaults_match_the_zen_rig(self):
        rig = DirectionProxyRig()
        cfg = rig.plan(SceneBounds())[0]
        assert cfg.type == LightType.SUN
        assert cfg.energy == 0.0
        assert cfg.rotation == (45.0, -35.0, 0.0)

    def test_rotation_radians_matches_shader_vector_rotate(self):
        # The zen file's Dot Creation node carries (0.785, -0.611, 0.0) radians;
        # the proxy sun must agree or the lamp lies about the light direction.
        rx, ry, rz = DirectionProxyRig().rotation_radians
        assert rx == pytest.approx(0.785, abs=1e-3)
        assert ry == pytest.approx(-0.611, abs=1e-3)
        assert rz == pytest.approx(0.0, abs=1e-9)


class TestOrbitPositions:
    def test_orbit_closes_without_duplicating_the_first_frame(self):
        b = SceneBounds(extent=2.0)
        pts = orbit_positions(b, num_frames=8)
        assert len(pts) == 8
        assert pts[0] != pts[-1]

    def test_orbit_is_planar_and_elevated(self):
        b = SceneBounds(center=(0, 0, 0), extent=2.0)
        pts = orbit_positions(b, num_frames=6, elevation_ratio=0.5)
        assert len({round(p[2], 9) for p in pts}) == 1
        assert pts[0][2] == pytest.approx(0.5)


class TestSetupScriptSerialization:
    def test_emitted_script_is_valid_python(self):
        b = SceneBounds(extent=2.0)
        configs = ArcRig(num_frames=3).plan_frames(b)
        script = lights_setup_script(configs)
        compile(script, "<generated>", "exec")  # must not raise

    def test_script_contains_no_logic_only_data(self):
        script = lights_setup_script(ThreePointRig().plan(SceneBounds(extent=2.0)))
        # Positions are baked in locally; the container gets no rig math.
        assert "math.cos" not in script
        assert "bpy.data.lights.new" in script

    def test_clear_flag_controls_the_wipe_preamble(self):
        configs = ThreePointRig().plan(SceneBounds(extent=2.0))
        assert "bpy.data.objects.remove" in lights_setup_script(configs, clear=True)
        assert "bpy.data.objects.remove" not in lights_setup_script(configs, clear=False)
