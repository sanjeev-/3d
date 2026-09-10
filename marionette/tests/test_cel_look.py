"""CelLook graph-spec tests. Pure — no Blender required."""

import math

import pytest

from marionette.looks import CelLook, CelParams, bridget_preset, zen_preset
from marionette.looks.cel import OWNER, _direction_vector, _warm_shadow


def _node_types(graph):
    return [n["bl_idname"] for n in graph.to_dict()["nodes"]]


def _node(graph, key):
    return next(n for n in graph.to_dict()["nodes"] if n["key"] == key)


class TestHardTerminator:
    def test_zero_smoothness_builds_a_hard_step(self):
        g = CelLook().build_graph()
        lit = _node(g, "lit")
        assert lit["bl_idname"] == "ShaderNodeMath"
        assert lit["props"]["operation"] == "GREATER_THAN"

    def test_nonzero_smoothness_switches_to_a_ramp(self):
        g = CelLook(CelParams(shadow_smoothness=0.25)).build_graph()
        lit = _node(g, "lit")
        assert lit["bl_idname"] == "ShaderNodeMapRange"
        assert lit["inputs"]["From Min"] == pytest.approx(0.5)
        assert lit["inputs"]["From Max"] == pytest.approx(0.75)

    def test_threshold_tracks_shadow_push(self):
        g = CelLook(CelParams(shadow_push=0.7)).build_graph()
        assert _node(g, "lit")["inputs"]["1"] == pytest.approx(0.7)

    def test_half_lambert_is_push_then_halve(self):
        g = CelLook().build_graph()
        assert _node(g, "pushed")["inputs"]["1"] == pytest.approx(1.0)
        assert _node(g, "half_lambert")["inputs"]["1"] == pytest.approx(0.5)


class TestShadowColor:
    def test_shadow_is_a_separate_color_not_a_darkened_base(self):
        base = (0.8, 0.7, 0.6, 1.0)
        g = CelLook().build_graph(base_color=base)
        bands = _node(g, "bands")
        shadow = bands["inputs"]["A"]
        # Not a uniform multiple of the base — that is the whole point.
        ratios = [shadow[i] / base[i] for i in range(3)]
        assert max(ratios) - min(ratios) > 0.05, ratios

    def test_shadow_is_warmer_than_the_base(self):
        r, g_, b, _ = _warm_shadow((0.5, 0.5, 0.5, 1.0))
        assert r > g_ and r > b, (r, g_, b)

    def test_shadow_is_darker_than_the_base(self):
        base = (0.6, 0.6, 0.6, 1.0)
        assert all(c < 0.6 for c in _warm_shadow(base)[:3])

    def test_explicit_shadow_color_is_honored(self):
        g = CelLook().build_graph(base_color=(1, 1, 1, 1), shadow_color=(0.1, 0.2, 0.3, 1.0))
        assert _node(g, "bands")["inputs"]["A"] == [0.1, 0.2, 0.3, 1.0]

    def test_bands_use_mix_not_a_blend(self):
        # MIX selects between two flat colors; anything else re-introduces
        # a gradient across the terminator.
        assert _node(CelLook().build_graph(), "bands")["props"]["blend_type"] == "MIX"


class TestRim:
    def test_rim_present_by_default_zen(self):
        assert "rim" in [n["key"] for n in CelLook().build_graph().to_dict()["nodes"]]

    def test_rim_absent_when_disabled_bridget(self):
        g = CelLook(bridget_preset()).build_graph()
        assert "rim" not in [n["key"] for n in g.to_dict()["nodes"]]

    def test_rim_intensity_is_applied(self):
        g = CelLook(CelParams(rim_intensity=0.33)).build_graph()
        assert _node(g, "rim_scaled")["inputs"]["1"] == pytest.approx(0.33)


class TestVertexMask:
    def test_absent_by_default(self):
        assert "vertex_mask" not in [n["key"] for n in CelLook().build_graph().to_dict()["nodes"]]

    def test_present_for_the_painted_preset(self):
        g = CelLook(bridget_preset()).build_graph()
        assert "vertex_mask" in [n["key"] for n in g.to_dict()["nodes"]]


class TestDetailOverlay:
    def test_detail_multiplies_last_before_emission(self):
        g = CelLook().build_graph()
        assert _node(g, "detail")["props"]["blend_type"] == "MULTIPLY"
        links = g.to_dict()["links"]
        assert {"from": ["detail", "Result"], "to": ["emission", "Color"]} in links

    def test_output_is_emission_so_eevee_lighting_is_bypassed(self):
        types = _node_types(CelLook().build_graph())
        assert "ShaderNodeEmission" in types
        assert "ShaderNodeBsdfPrincipled" not in types


class TestDirectionVector:
    def test_is_unit_length(self):
        for rot in [(45, -35, 0), (0, 0, 0), (90, 12, 30), (-20, 140, 0)]:
            v = _direction_vector(rot)
            assert math.isclose(math.sqrt(sum(c * c for c in v)), 1.0, rel_tol=1e-9)

    def test_zero_rotation_points_up(self):
        # An unrotated sun shines down; the shader wants the reverse.
        assert _direction_vector((0, 0, 0)) == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)

    def test_pitch_tilts_toward_minus_y(self):
        assert _direction_vector((45, 0, 0))[1] < 0


class TestGraphHygiene:
    def test_owner_is_namespaced(self):
        assert CelLook().build_graph().owner == OWNER == "marionette.cel"

    def test_output_node_is_adopted_not_owned(self):
        assert _node(CelLook().build_graph(), "output")["adopt"] is True

    def test_spec_is_json_serializable(self):
        import json

        json.dumps(CelLook().build_graph().to_dict())

    def test_requires_standard_view_transform(self):
        assert CelLook.requirements.view_transform == "Standard"

    def test_presets_produce_different_graphs(self):
        zen = CelLook(zen_preset()).build_graph().to_dict()
        bridget = CelLook(bridget_preset()).build_graph().to_dict()
        assert zen != bridget
