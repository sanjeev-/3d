"""Light rigs — composable lighting strategies.

Mirrors the ``CameraMovement`` pattern: an ABC with concrete strategies, applied
to a scene. The split here is deliberate:

    plan(bounds) -> [LightConfig]    pure, unit-testable without Blender
    apply(scene) -> [Light]          realizes the plan via bpy

That keeps rig math out of Blender and lets a plan be serialized and shipped to
a render container instead of generating Python source as a string.
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Iterable, List, Optional, Sequence, Tuple

from .configs import HDRIConfig, LightConfig, LightType

if TYPE_CHECKING:  # pragma: no cover
    from .lighting import Light

Vec3 = Tuple[float, float, float]


@dataclass(frozen=True)
class SceneBounds:
    """Axis-aligned summary of what a rig is lighting."""

    center: Vec3 = (0.0, 0.0, 0.0)
    extent: float = 1.0  # largest dimension across all axes

    @property
    def radius(self) -> float:
        """A comfortable orbit radius for the subject."""
        return max(self.extent, 1e-6) * 0.5

    @classmethod
    def from_points(cls, points: Iterable[Vec3]) -> "SceneBounds":
        """Compute bounds from world-space corner points. Pure."""
        pts = list(points)
        if not pts:
            return cls()
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        center = (
            (min(xs) + max(xs)) / 2.0,
            (min(ys) + max(ys)) / 2.0,
            (min(zs) + max(zs)) / 2.0,
        )
        extent = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
        return cls(center=center, extent=extent)

    @classmethod
    def from_scene(cls, scene=None, skip_dim: Optional[float] = None) -> "SceneBounds":
        """Compute bounds from mesh objects in a live scene. Requires bpy.

        Args:
            skip_dim: Ignore meshes whose largest dimension exceeds this, so
                floors and backdrops do not swamp the subject.
        """
        import bpy  # noqa: PLC0415
        import mathutils  # noqa: PLC0415

        target = scene or bpy.context.scene
        points: List[Vec3] = []
        for obj in target.objects:
            if obj.type != "MESH":
                continue
            corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
            if skip_dim is not None:
                size = max(
                    max(v.x for v in corners) - min(v.x for v in corners),
                    max(v.y for v in corners) - min(v.y for v in corners),
                    max(v.z for v in corners) - min(v.z for v in corners),
                )
                if size > skip_dim:
                    continue
            points.extend((v.x, v.y, v.z) for v in corners)
        return cls.from_points(points)


class LightRig(ABC):
    """Abstract base for all lighting strategies."""

    name: ClassVar[str] = "rig"

    def __init__(self, replace_existing: bool = True):
        self.replace_existing = replace_existing

    @abstractmethod
    def plan(self, bounds: SceneBounds) -> List[LightConfig]:
        """Return the lights this rig wants, given the subject bounds. Pure."""

    def apply(self, scene=None, bounds: Optional[SceneBounds] = None) -> List["Light"]:
        """Realize :meth:`plan` in Blender. Requires bpy."""
        from .lighting import Light, clear_lights  # noqa: PLC0415

        if self.replace_existing:
            clear_lights()
        resolved = bounds if bounds is not None else SceneBounds.from_scene(scene)
        return [Light.create(cfg) for cfg in self.plan(resolved)]


class ThreePointRig(LightRig):
    """Classic key / fill / rim setup, scaled to the subject."""

    name = "three_point"

    def __init__(
        self,
        key_energy: float = 1000.0,
        fill_ratio: float = 0.35,
        rim_ratio: float = 0.6,
        key_azimuth: float = 45.0,
        key_elevation: float = 30.0,
        distance_multiplier: float = 2.0,
        light_type: LightType = LightType.AREA,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.key_energy = key_energy
        self.fill_ratio = fill_ratio
        self.rim_ratio = rim_ratio
        self.key_azimuth = key_azimuth
        self.key_elevation = key_elevation
        self.distance_multiplier = distance_multiplier
        self.light_type = light_type

    def _place(self, bounds: SceneBounds, azimuth: float, elevation: float) -> Vec3:
        r = bounds.radius * self.distance_multiplier
        az = math.radians(azimuth)
        el = math.radians(elevation)
        cx, cy, cz = bounds.center
        return (
            cx + r * math.cos(el) * math.cos(az),
            cy + r * math.cos(el) * math.sin(az),
            cz + r * math.sin(el),
        )

    def plan(self, bounds: SceneBounds) -> List[LightConfig]:
        size = max(bounds.radius, 1e-6)
        return [
            LightConfig(
                name="Key",
                type=self.light_type,
                energy=self.key_energy,
                location=self._place(bounds, self.key_azimuth, self.key_elevation),
                size=size,
            ),
            LightConfig(
                name="Fill",
                type=self.light_type,
                energy=self.key_energy * self.fill_ratio,
                location=self._place(bounds, self.key_azimuth - 110.0, self.key_elevation * 0.4),
                size=size * 1.5,
            ),
            LightConfig(
                name="Rim",
                type=self.light_type,
                energy=self.key_energy * self.rim_ratio,
                location=self._place(bounds, self.key_azimuth + 170.0, self.key_elevation + 25.0),
                size=size * 0.6,
            ),
        ]


class ArcRig(LightRig):
    """Sweeps a single light along a hemispheric arc — a lighting study.

    Ported from ``scripts/demos/lighting/light_arc_modal.py``, where this math
    lived inside a generated Blender script.
    """

    name = "arc"

    def __init__(
        self,
        axis: str = "x",
        num_frames: int = 24,
        energy: float = 3000.0,
        radius_multiplier: float = 2.0,
        light_type: LightType = LightType.POINT,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if axis not in ("x", "y", "fixed"):
            raise ValueError(f"axis must be 'x', 'y' or 'fixed'; got {axis!r}")
        self.axis = axis
        self.num_frames = max(1, num_frames)
        self.energy = energy
        self.radius_multiplier = radius_multiplier
        self.light_type = light_type

    def position_at(self, bounds: SceneBounds, frame_index: int) -> Vec3:
        """Light position for ``frame_index`` along the arc. Pure."""
        cx, cy, cz = bounds.center
        r = bounds.radius * self.radius_multiplier
        if self.axis == "fixed":
            return (cx, cy, cz + r)
        theta = math.pi * frame_index / max(1, self.num_frames - 1)
        if self.axis == "x":
            return (cx + r * math.cos(theta), cy, cz + r * math.sin(theta))
        return (cx, cy + r * math.cos(theta), cz + r * math.sin(theta))

    def plan(self, bounds: SceneBounds) -> List[LightConfig]:
        return [
            LightConfig(
                name=f"ArcLight_{self.axis}",
                type=self.light_type,
                energy=self.energy,
                location=self.position_at(bounds, 0),
            )
        ]

    def plan_frames(self, bounds: SceneBounds) -> List[LightConfig]:
        """One LightConfig per frame — for per-frame render fan-out. Pure."""
        base = self.plan(bounds)[0]
        return [
            base.model_copy(update={"location": self.position_at(bounds, i)})
            for i in range(self.num_frames)
        ]

    def apply(self, scene=None, bounds: Optional[SceneBounds] = None) -> List["Light"]:
        """Create the light and keyframe it along the arc."""
        lights = super().apply(scene=scene, bounds=bounds)
        resolved = bounds if bounds is not None else SceneBounds.from_scene(scene)
        light = lights[0]
        for i in range(self.num_frames):
            light.location = self.position_at(resolved, i)
            light.keyframe("location", frame=i, interpolation="LINEAR")
        return lights


class DirectionProxyRig(LightRig):
    """A single sun that exists to *carry a direction*, not to illuminate.

    Both analyzed anime rigs use this: the shader computes its own N·L from a
    rotation constant, and a sun object mirrors that rotation so artists have
    something to grab in the viewport. Zenitsu's is literally named
    ``Sun [[ DO NOT DELETE ]]``.

    Keep ``energy`` at 0.0 when the shader is fully self-lit.
    """

    name = "direction_proxy"

    def __init__(
        self,
        rotation: Vec3 = (45.0, -35.0, 0.0),
        energy: float = 0.0,
        light_name: str = "Sun [[ direction proxy ]]",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.rotation = rotation
        self.energy = energy
        self.light_name = light_name

    @property
    def rotation_radians(self) -> Vec3:
        """The value a shader's Vector Rotate node should carry. Pure."""
        return tuple(math.radians(r) for r in self.rotation)  # type: ignore[return-value]

    def plan(self, bounds: SceneBounds) -> List[LightConfig]:
        return [
            LightConfig(
                name=self.light_name,
                type=LightType.SUN,
                energy=self.energy,
                location=bounds.center,
                rotation=self.rotation,
            )
        ]


class HDRIRig(LightRig):
    """World-based image lighting, built through :class:`NodeGraph`.

    Replaces the hand-wired node plumbing that previously lived in
    ``Scene.set_hdri``.
    """

    name = "hdri"
    OWNER = "marionette.hdri"

    def __init__(self, config: HDRIConfig, **kwargs):
        kwargs.setdefault("replace_existing", False)
        super().__init__(**kwargs)
        self.config = config

    def plan(self, bounds: SceneBounds) -> List[LightConfig]:
        """An HDRI adds no lamp objects."""
        return []

    def build_graph(self, image_loader=None):
        """Build the world node graph spec. Pure unless ``image_loader`` runs."""
        from .shading.graph import NodeGraph  # noqa: PLC0415

        graph = NodeGraph(self.OWNER)
        mapping = graph.node(
            "ShaderNodeMapping",
            "mapping",
            inputs={"Rotation": (0.0, 0.0, math.radians(self.config.rotation))},
        )
        tex_coord = graph.node("ShaderNodeTexCoord", "tex_coord")
        env = graph.node("ShaderNodeTexEnvironment", "env")
        if image_loader is not None:
            env_spec = graph.spec("env")
            env_spec.props["image"] = image_loader
        # Adopt the world's default Background node rather than creating a
        # second, disconnected one beside it.
        background = graph.node(
            "ShaderNodeBackground",
            "background",
            adopt=True,
            inputs={"Strength": self.config.strength},
        )
        output = graph.node("ShaderNodeOutputWorld", "output", adopt=True)

        graph.link(tex_coord.out("Generated"), mapping.inp("Vector"))
        graph.link(mapping.out("Vector"), env.inp("Vector"))
        graph.link(env.out("Color"), background.inp("Color"))
        graph.link(background.out("Background"), output.inp("Surface"))
        return graph

    def apply(self, scene=None, bounds: Optional[SceneBounds] = None) -> List["Light"]:
        """Set up the world. Requires bpy. Returns an empty list (no lamps)."""
        import os  # noqa: PLC0415

        import bpy  # noqa: PLC0415

        if not os.path.exists(self.config.path):
            raise FileNotFoundError(f"HDRI file not found: {self.config.path}")

        target = scene or bpy.context.scene
        world = target.world
        if not world:
            world = bpy.data.worlds.new("World")
            target.world = world
        world.use_nodes = True

        path = self.config.path
        self.build_graph(image_loader=lambda: bpy.data.images.load(path, check_existing=True)).build(
            world.node_tree
        )
        return []


def orbit_positions(
    bounds: SceneBounds,
    num_frames: int,
    radius_multiplier: float = 1.2,
    elevation_ratio: float = 0.4,
) -> List[Vec3]:
    """Camera positions for a full horizontal orbit. Pure.

    Uses ``num_frames`` (not ``num_frames - 1``) as the divisor so the last
    frame does not duplicate the first — the loop closes cleanly.
    """
    cx, cy, cz = bounds.center
    r = bounds.radius * radius_multiplier
    z = cz + bounds.radius * elevation_ratio
    out = []
    for i in range(num_frames):
        phi = 2.0 * math.pi * i / max(1, num_frames)
        out.append((cx + r * math.cos(phi), cy + r * math.sin(phi), z))
    return out


def lights_setup_script(configs: Sequence[LightConfig], clear: bool = True) -> str:
    """Emit a self-contained Blender-Python snippet that creates ``configs``.

    This is the serialization path for remote rendering: plan the rig locally
    with real Python, then ship *data* rather than generated logic.
    """
    lines = ["import bpy", "import math", ""]
    if clear:
        lines += [
            "for _o in list(bpy.data.objects):",
            "    if _o.type == 'LIGHT':",
            "        bpy.data.objects.remove(_o, do_unlink=True)",
            "for _l in list(bpy.data.lights):",
            "    if _l.users == 0:",
            "        bpy.data.lights.remove(_l)",
            "",
        ]
    for i, cfg in enumerate(configs):
        rot = tuple(math.radians(r) for r in cfg.rotation)
        lines += [
            f"_d = bpy.data.lights.new(name={cfg.name!r}, type={cfg.type.value!r})",
            f"_d.energy = {cfg.energy!r}",
            f"_d.color = {tuple(cfg.color)!r}",
            f"_d.use_shadow = {cfg.use_shadow!r}",
            f"_o{i} = bpy.data.objects.new(name={cfg.name!r}, object_data=_d)",
            f"bpy.context.collection.objects.link(_o{i})",
            f"_o{i}.location = {tuple(cfg.location)!r}",
            f"_o{i}.rotation_euler = {rot!r}",
            "",
        ]
    return "\n".join(lines).strip()
