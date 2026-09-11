"""Golden-image regression across looks.

Run normally to check for drift:

    .venv313/bin/python -m pytest marionette/tests/blender/test_golden.py

Approve an intentional change by regenerating the references, then review the
image diff before committing:

    .venv313/bin/python -m pytest marionette/tests/blender/test_golden.py --update-golden
"""

import pytest

bpy = pytest.importorskip("bpy")

from marionette.looks import (
    CelLook,
    CelParams,
    Look,
    LookPipeline,
    available_looks,
    bridget_preset,
    look_class,
    zen_preset,
)
from marionette.shading import MaterialRole, RoleMap, Selector

from .golden import VIEWS, compare, golden_path, build_scene, load_pixels, render_view

ROLES = RoleMap(
    {
        MaterialRole.SKIN: Selector(names=("body",)),
        MaterialRole.HAIR: Selector(names=("hair",)),
        MaterialRole.CLOTH: Selector(names=("cloth",)),
    }
)

#: A light across the view so terminators cross the subjects rather than
#: hiding behind them.
SIDE_LIT = zen_preset().model_copy(update={"light_direction": (25.0, 70.0, 0.0)})


class Case:
    """One look configuration with committed reference renders."""

    def __init__(self, name, look_name, factory, max_changed=0.002):
        self.name = name
        self.look_name = look_name
        self.factory = factory
        #: Fraction of pixels allowed to differ. Cel renders are deterministic,
        #: so an unchanged look scores exactly 0.0; this leaves only a sliver
        #: of room for platform differences in edge antialiasing.
        self.max_changed = max_changed

    def __repr__(self):
        return self.name


CASES = [
    Case("cel_zen", "cel", lambda: CelLook(SIDE_LIT)),
    Case("cel_bridget", "cel", lambda: CelLook(bridget_preset())),
    Case(
        "cel_smooth", "cel",
        lambda: CelLook(SIDE_LIT.model_copy(update={"shadow_smoothness": 0.6})),
    ),
    Case("cel_outline", "cel", lambda: CelLook(SIDE_LIT, outline_thickness=0.05)),
]

CASES_BY_NAME = {case.name: case for case in CASES}


@pytest.fixture
def golden_scene():
    return build_scene()


def _render_case(case, scene, tmp_path, view):
    LookPipeline(case.factory(), roles=ROLES).apply(scene)
    return render_view(scene, view, tmp_path / f"{case.name}_{view:02d}.exr")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
@pytest.mark.parametrize("view", range(VIEWS))
def test_look_matches_golden(case, view, golden_scene, tmp_path, request):
    update = request.config.getoption("--update-golden")
    reference = golden_path(case.name, view)

    rendered_path = _render_case(case, golden_scene, tmp_path, view)

    if update or not reference.exists():
        reference.parent.mkdir(parents=True, exist_ok=True)
        reference.write_bytes(rendered_path.read_bytes())
        if not update:
            pytest.fail(
                f"no reference for {case.name} view {view}; wrote one to {reference}. "
                "Inspect it, then commit it to accept this as the baseline."
            )
        pytest.skip(f"updated reference {reference.name}")

    diff = compare(load_pixels(rendered_path), load_pixels(reference))
    assert diff.changed_fraction <= case.max_changed, (
        f"{case.name} view {view} drifted: {diff}, above the "
        f"{case.max_changed:.2%} budget. If this change is intended, re-run "
        f"with --update-golden and review the new reference before committing."
    )


class TestHarness:
    """Guards on the harness itself, so a passing suite means something."""

    def test_scene_is_deterministic(self, golden_scene, tmp_path):
        """Two renders of the same look must be bit-comparable."""
        case = CASES_BY_NAME["cel_zen"]
        first = load_pixels(_render_case(case, golden_scene, tmp_path / "a", 0))
        build_scene()
        second = load_pixels(_render_case(case, bpy.context.scene, tmp_path / "b", 0))

        diff = compare(first, second)
        assert diff.max_abs == 0.0, f"scene construction is not reproducible: {diff}"

    def test_comparison_detects_a_real_change(self, golden_scene, tmp_path):
        """The metric must actually move when the look changes.

        Without this, a comparison that always returned zero would make every
        golden test pass forever.
        """
        zen = _render_case(CASES_BY_NAME["cel_zen"], golden_scene, tmp_path / "zen", 0)
        zen_px = load_pixels(zen)

        build_scene()
        shifted = CelParams(**{**SIDE_LIT.model_dump(), "shadow_push": 0.8})
        LookPipeline(CelLook(shifted), roles=ROLES).apply(bpy.context.scene)
        moved = render_view(bpy.context.scene, 0, tmp_path / "moved.exr")

        diff = compare(zen_px, load_pixels(moved))
        # Moving the terminator repaints a band. The mean barely registers it,
        # which is exactly why changed_fraction is the metric under test here.
        assert diff.changed_fraction > 0.01, diff

    def test_size_mismatch_is_reported_clearly(self):
        with pytest.raises(ValueError, match="different resolution"):
            compare([0.0] * 8, [0.0] * 4)

    def test_every_material_building_look_has_a_case(self):
        """New looks that build shaders must not escape golden coverage.

        Looks that only configure render settings (PBRLook) are covered by
        direct assertions instead; a look that emits a *shader* needs pixels.
        """
        covered = {case.look_name for case in CASES}
        for name in available_looks():
            cls = look_class(name)
            builds_materials = cls.build_materials is not Look.build_materials
            if builds_materials:
                assert name in covered, (
                    f"look {name!r} builds materials but has no golden case; "
                    f"add one to CASES in {__file__}"
                )
