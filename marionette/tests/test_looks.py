"""Look, registry, params and selector tests. Pure — no Blender required."""

import pytest

from marionette.looks import (
    BPY_UNAVAILABLE,
    STAGES,
    CelParams,
    Look,
    LookContext,
    LookPipeline,
    LookRequirements,
    LookValidationError,
    available_looks,
    bridget_preset,
    get_look,
    register_look,
    zen_preset,
)
from marionette.shading import MaterialRole, ObjectInfo, RoleMap, Selector, anime_character_roles


class TestCelParamsZenDefaults:
    """Defaults encode the zen configuration; see looks/params.py."""

    def test_specular_is_off_by_default(self):
        p = zen_preset()
        assert p.specular_size == 0.0
        assert p.specular_enabled is False

    def test_terminator_sits_at_the_geometric_horizon(self):
        p = zen_preset()
        # half-lambert with push 1.0, thresholded at 0.5, is exactly N·L >= 0
        assert p.light_push == 1.0
        assert p.shadow_push == 0.5

    def test_edges_are_hard(self):
        assert zen_preset().shadow_smoothness == 0.0

    def test_no_painted_control_data(self):
        p = zen_preset()
        assert p.use_offset_map is False
        assert p.use_vertex_shadow_mask is False

    def test_rims_are_on_but_subtle(self):
        p = zen_preset()
        assert p.rim_enabled is True
        assert p.rim_intensity == pytest.approx(0.1)
        assert p.shadow_rim_intensity == pytest.approx(0.1)

    def test_light_direction_matches_the_proxy_sun(self):
        assert zen_preset().light_direction == (45.0, -35.0, 0.0)


class TestBridgetPreset:
    def test_differs_from_zen_in_the_expected_places(self):
        zen, bridget = zen_preset(), bridget_preset()
        assert bridget.specular_enabled and not zen.specular_enabled
        assert bridget.use_offset_map and not zen.use_offset_map
        assert bridget.rim_enabled is False and zen.rim_enabled is True

    def test_shares_the_same_terminator_math(self):
        # Same shader group, same core thresholds — only the inputs differ.
        zen, bridget = zen_preset(), bridget_preset()
        assert zen.shadow_push == bridget.shadow_push
        assert zen.shadow_smoothness == bridget.shadow_smoothness


class TestShaderInputMapping:
    def test_maps_onto_real_socket_names(self):
        inputs = zen_preset().as_shader_inputs()
        assert inputs["Shadow 1 Push"] == 0.5
        assert inputs["Specular Size"] == 0.0
        assert inputs["Highlight Rimlight Intensity"] == pytest.approx(0.1)

    def test_every_mapped_socket_exists_in_the_reference_shader(self):
        # Socket names captured from the Arc System Works - Strive group.
        known = {
            "Global Light Push", "Shadow 1 Push", "Shadow 1 Smoothness",
            "Shadow 1 Vertex Threshold", "Shadow 2 Push", "Shadow 2 Smoothness",
            "Shadow 2 Vertex Threshold", "Permanent Shadow Threshold",
            "Specular Size", "Specular Intensity", "Highlight Rimlight Size",
            "Highlight Rimlight Intensity", "Shadow Rimlight Size",
            "Shadow Rimlight Intensity", "Base Intensity", "Shadow 1 Intensity",
        }
        assert set(zen_preset().as_shader_inputs()) <= known


class TestSelectors:
    def test_glob_and_exact_matching(self):
        s = Selector(patterns=("*face*",), names=("exact_name",))
        assert s.matches(ObjectInfo("5_face_0.1_16_16"))
        assert s.matches(ObjectInfo("exact_name"))
        assert not s.matches(ObjectInfo("5_hair_0"))

    def test_collection_and_material_matching(self):
        s = Selector(collections=("Bgt DR Mesh",), materials=("zen hair",))
        assert s.matches(ObjectInfo("x", collections=("Bgt DR Mesh",)))
        assert s.matches(ObjectInfo("y", materials=("zen hair",)))
        assert not s.matches(ObjectInfo("z"))

    def test_empty_selector_matches_nothing(self):
        assert Selector().is_empty
        assert not Selector().matches(ObjectInfo("anything"))

    def test_role_resolution_is_order_sensitive(self):
        # Outline duplicates must be claimed before the broad body patterns,
        # otherwise "body out" is mistaken for skin geometry.
        roles = anime_character_roles()
        resolved = roles.resolve(
            [
                ObjectInfo("body out"),
                ObjectInfo("5_body_0.1_16_16"),
                ObjectInfo("7_faceLINES_0.1_16_16"),
                ObjectInfo("5_face_0.1_16_16"),
                ObjectInfo("5_hair_0.1_16_16"),
            ]
        )
        assert resolved[MaterialRole.OUTLINE] == ["body out"]
        assert resolved[MaterialRole.LINEART] == ["7_faceLINES_0.1_16_16"]
        assert resolved[MaterialRole.SKIN] == ["5_body_0.1_16_16"]
        assert resolved[MaterialRole.FACE] == ["5_face_0.1_16_16"]
        assert resolved[MaterialRole.HAIR] == ["5_hair_0.1_16_16"]

    def test_handles_both_analyzed_naming_schemes(self):
        roles = anime_character_roles()
        assert roles.role_for(ObjectInfo("bgtDR_face")) == MaterialRole.FACE
        assert roles.role_for(ObjectInfo("5_face_0.1_16_16")) == MaterialRole.FACE

    def test_unmatched_objects_are_dropped(self):
        resolved = RoleMap({MaterialRole.FACE: Selector(patterns=("*face*",))}).resolve(
            [ObjectInfo("nothing_relevant")]
        )
        assert resolved[MaterialRole.FACE] == []


class TestRegistry:
    def test_builtin_looks_are_registered(self):
        assert "pbr" in available_looks()
        assert "studio" in available_looks()

    def test_get_look_instantiates(self):
        look = get_look("pbr")
        assert look.name == "pbr"

    def test_unknown_look_raises_with_suggestions(self):
        with pytest.raises(KeyError, match="available"):
            get_look("no-such-look")

    def test_duplicate_registration_rejected(self):
        @register_look("temp-look-for-test")
        class _A(Look):
            name = "temp-look-for-test"

        with pytest.raises(ValueError, match="already registered"):

            @register_look("temp-look-for-test")
            class _B(Look):
                name = "temp-look-for-test"


class TestPipeline:
    def test_stage_order_is_stable(self):
        assert STAGES == (
            "configure_render",
            "prepare_geometry",
            "build_materials",
            "build_lighting",
            "build_passes",
            "build_compositor",
        )

    def test_base_stages_are_no_ops(self):
        look = Look()
        ctx = LookContext()
        for stage in STAGES:
            getattr(look, stage)(None, ctx)  # must not raise

    def test_unknown_skip_stage_rejected(self):
        with pytest.raises(ValueError, match="unknown stage"):
            LookPipeline(get_look("pbr"), skip=("not_a_stage",))

    def test_outside_blender_reports_rather_than_crashing(self, monkeypatch):
        # Deterministic regardless of whether bpy is installed: assert the
        # pipeline's handling of the sentinel, not the interpreter's contents.
        look = get_look("pbr")
        monkeypatch.setattr(look, "validate", lambda scene=None: [BPY_UNAVAILABLE])
        result = LookPipeline(look).apply(strict=True)
        assert result.stages_run == []
        assert result.stages_skipped == list(STAGES)
        assert result.warnings == [BPY_UNAVAILABLE]

    def test_real_validation_failures_still_raise_in_strict_mode(self, monkeypatch):
        # A bare Look has no-op stages, so this exercises validation alone and
        # stays runnable on interpreters without bpy.
        look = Look()
        monkeypatch.setattr(look, "validate", lambda scene=None: ["engine is wrong"])
        with pytest.raises(LookValidationError, match="engine is wrong"):
            LookPipeline(look).apply(strict=True)
        # Non-strict runs report the problem and continue.
        result = LookPipeline(look).apply(strict=False)
        assert result.warnings == ["engine is wrong"]
        assert result.stages_run == list(STAGES)

    def test_context_reports_unmatched_roles_as_empty(self):
        ctx = LookContext()
        assert ctx.objects_for(MaterialRole.FACE) == []


class TestRequirements:
    def test_requirements_are_declarative(self):
        req = LookRequirements(engine="BLENDER_EEVEE_NEXT", view_transform="Standard")
        assert req.engine == "BLENDER_EEVEE_NEXT"
        assert req.addons == ()
