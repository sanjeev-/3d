"""The Look abstraction — a render style spanning every layer that produces it.

Analyzing two production anime rigs showed that a "lighting technique" is never
just lights. Both files coordinate: geometry prep (custom normals, outline hulls,
line meshes), materials, a light rig, passes, compositing, and render settings.
A Look owns all six, and every stage has a no-op default so a simple look
overrides one method while a full NPR look overrides all of them.
"""

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from ..shading.selectors import MaterialRole, RoleMap

#: Stage methods, in execution order.
STAGES: Tuple[str, ...] = (
    "configure_render",
    "prepare_geometry",
    "build_materials",
    "build_lighting",
    "build_passes",
    "build_compositor",
)


#: Reported by :meth:`Look.validate` when running outside Blender entirely.
#: The pipeline treats this as "nothing to configure" rather than a failure.
BPY_UNAVAILABLE = "bpy unavailable — cannot validate outside Blender"


class LookValidationError(RuntimeError):
    """Raised when a scene cannot support the requested look."""


class LookParams(BaseModel):
    """Default (empty) parameter model, so a bare Look is instantiable."""


class LookRequirements(BaseModel):
    """What a look needs in order to produce its intended output.

    Both analyzed rigs fail *silently* when these are unmet — a missing line
    renderer drops outlines with no error, and a filmic view transform quietly
    destroys flat cel colors. A look that cannot produce its output should
    refuse to run rather than render something plausible but wrong.
    """

    engine: Optional[str] = Field(default=None, description="Required render engine id")
    view_transform: Optional[str] = Field(
        default=None, description="Required color management view transform"
    )
    addons: Tuple[str, ...] = Field(default=(), description="Required addon module names")
    node_groups: Tuple[str, ...] = Field(
        default=(), description="Node groups that must exist in the blend file"
    )


@dataclass
class LookContext:
    """Carried through every stage so they can share resolved state."""

    roles: RoleMap = field(default_factory=RoleMap)
    resolved: Dict[MaterialRole, List[str]] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)

    def objects_for(self, role: MaterialRole) -> List[str]:
        """Object names bound to ``role``; empty if the role went unmatched."""
        return self.resolved.get(role, [])


@dataclass
class LookResult:
    """What a pipeline run did."""

    look: str
    stages_run: List[str] = field(default_factory=list)
    stages_skipped: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    context: Optional[LookContext] = None


class Look(ABC):
    """Base class for render styles.

    Subclasses set ``name``, optionally ``requirements``, and override whichever
    stages they need. Stage signatures are uniform — ``(scene, ctx)`` — so the
    pipeline can drive them generically.
    """

    name: ClassVar[str] = "look"
    requirements: ClassVar[LookRequirements] = LookRequirements()
    params_model: ClassVar[type] = LookParams

    def __init__(self, params: Optional[BaseModel] = None):
        if params is None:
            params = self.params_model()
        elif isinstance(params, dict):
            params = self.params_model(**params)
        self.params = params

    # -- validation ---------------------------------------------------------

    def validate(self, scene=None) -> List[str]:
        """Preconditions the look cannot fix for itself. Empty means good to go.

        Only things outside the look's control belong here — a missing addon or
        node group. Engine and view transform are deliberately NOT preconditions:
        ``configure_render`` sets them, so checking beforehand would make a look
        that fixes a scene refuse to run on that scene. They are postconditions,
        checked by :meth:`verify`.
        """
        try:
            import bpy  # noqa: PLC0415
        except ImportError:
            return [BPY_UNAVAILABLE]

        problems: List[str] = []
        req = self.requirements

        for addon in req.addons:
            if addon not in bpy.context.preferences.addons:
                problems.append(f"required addon {addon!r} is not enabled")
        for group in req.node_groups:
            if group not in bpy.data.node_groups:
                problems.append(f"required node group {group!r} not found in this blend file")
        return problems

    def verify(self, scene=None) -> List[str]:
        """Postconditions, checked after the stages have run.

        These are settings the look configures itself, so a failure means the
        scene will render wrong — usually because ``configure_render`` was
        skipped. Catching it matters: a cel look rendered through AgX yields a
        plausible image that is quietly not the intended look.
        """
        try:
            import bpy  # noqa: PLC0415
        except ImportError:
            return [BPY_UNAVAILABLE]

        problems: List[str] = []
        req = self.requirements
        target = scene or bpy.context.scene

        if req.engine and target.render.engine != req.engine:
            problems.append(
                f"engine is {target.render.engine!r}, look {self.name!r} requires {req.engine!r}"
            )
        if req.view_transform and target.view_settings.view_transform != req.view_transform:
            problems.append(
                f"view transform is {target.view_settings.view_transform!r}, "
                f"look {self.name!r} requires {req.view_transform!r}"
            )
        return problems

    def default_roles(self) -> RoleMap:
        """RoleMap used when the caller does not supply one."""
        return RoleMap()

    # -- stages (override what you need) ------------------------------------

    def configure_render(self, scene, ctx: LookContext) -> None:
        """Engine, sampling, resolution, color management."""

    def prepare_geometry(self, scene, ctx: LookContext) -> None:
        """Normals, vertex data, outline hulls, line meshes, shadow proxies."""

    def build_materials(self, scene, ctx: LookContext) -> None:
        """Shader graphs, per role."""

    def build_lighting(self, scene, ctx: LookContext) -> None:
        """Lamps, world, direction proxies."""

    def build_passes(self, scene, ctx: LookContext) -> None:
        """View layers and AOVs."""

    def build_compositor(self, scene, ctx: LookContext) -> None:
        """Post-processing graph. Optional — Zenitsu's rig uses none at all."""


class LookPipeline:
    """Runs a look's stages in order, with per-run skipping."""

    def __init__(self, look: Look, roles: Optional[RoleMap] = None, skip: Sequence[str] = ()):
        unknown = set(skip) - set(STAGES)
        if unknown:
            raise ValueError(f"unknown stage(s) to skip: {sorted(unknown)}")
        self.look = look
        self.roles = roles
        self.skip = tuple(skip)

    def apply(self, scene=None, strict: bool = True, resolve_roles: bool = True) -> LookResult:
        """Run the pipeline. Raises LookValidationError when ``strict``."""
        problems = self.look.validate(scene)
        # Outside Blender there is nothing to configure; surface it as a warning
        # rather than a hard failure so specs stay inspectable in plain pytest.
        outside_blender = problems == [BPY_UNAVAILABLE]
        if problems and strict and not outside_blender:
            raise LookValidationError(
                f"look {self.look.name!r} cannot run:\n  - " + "\n  - ".join(problems)
            )

        roles = self.roles if self.roles is not None else self.look.default_roles()
        ctx = LookContext(roles=roles)
        result = LookResult(look=self.look.name, warnings=list(problems), context=ctx)

        if outside_blender:
            result.stages_skipped = list(STAGES)
            return result

        if resolve_roles and roles.roles:
            ctx.resolved = roles.resolve_scene(scene)

        for stage in STAGES:
            if stage in self.skip:
                result.stages_skipped.append(stage)
                continue
            getattr(self.look, stage)(scene, ctx)
            result.stages_run.append(stage)

        unmet = self.look.verify(scene)
        if unmet and unmet != [BPY_UNAVAILABLE]:
            if strict:
                raise LookValidationError(
                    f"look {self.look.name!r} did not reach its required state:\n  - "
                    + "\n  - ".join(unmet)
                )
            result.warnings.extend(unmet)

        return result
