"""CelLook — anime/cel shading built from first principles with NodeGraph.

This is the transferable core of the two production rigs analyzed for this
library, reimplemented rather than copied. The shading math, in one line:

    ModifiedNdotL = clamp(0.5 * vertex_mask * (N·L + light_push) + offset)
    lit           = ModifiedNdotL >= shadow_push          # hard step
    color         = lit ? base : shadow_color             # no blending
    color        += rim  (thresholded on N·V)
    color        *= detail                                # painted overlay

Four decisions make it read as 2D rather than 3D, and all four are defaults:

1. Shadow color is its own input, not ``base * factor``. Cel painting picks a
   shadow hue; it does not darken the base.
2. The terminator is a hard step. ``shadow_smoothness = 0`` selects
   GREATER_THAN over a smooth MapRange.
3. Light direction comes from a rotation constant, not a lamp. A zero-energy
   sun mirrors it so artists have something to grab (DirectionProxyRig).
4. Detail arrives as a multiply overlay — hand-drawn artwork on top of flat
   computed shading, never computed lighting.

Requires a Standard view transform: a filmic/AgX curve rolls off exactly the
flat highlights this look depends on, so ``validate()`` refuses to run without
it rather than rendering something plausible but wrong.
"""

import math
from typing import Optional

from ..configs import LightType
from ..rigs import DirectionProxyRig
from ..shading.graph import NodeGraph
from ..shading.selectors import MaterialRole, RoleMap, Selector, anime_character_roles
from .base import Look, LookContext, LookRequirements
from .params import CelParams
from .registry import register_look

#: Owner key for every node graph this look builds.
OWNER = "marionette.cel"

#: Roles that receive the cel shader. Outline/lineart meshes are handled by the
#: geometry stage, and eyes are deliberately left alone — both analyzed rigs
#: shade eyes with a conventional BSDF.
SHADED_ROLES = (
    MaterialRole.SKIN,
    MaterialRole.FACE,
    MaterialRole.HAIR,
    MaterialRole.CLOTH,
    MaterialRole.PROP,
)


@register_look("cel")
class CelLook(Look):
    """Hard-edged cel shading. Defaults are the ``zen`` preset."""

    name = "cel"
    params_model = CelParams
    requirements = LookRequirements(view_transform="Standard")

    def __init__(
        self,
        params: Optional[CelParams] = None,
        outline_thickness: float = 0.0,
        engine: str = "BLENDER_EEVEE",
        samples: int = 64,
    ):
        super().__init__(params)
        self.outline_thickness = outline_thickness
        self.engine = engine
        self.samples = samples

    def default_roles(self) -> RoleMap:
        return anime_character_roles()

    # -- stages -------------------------------------------------------------

    def configure_render(self, scene, ctx: LookContext) -> None:
        import bpy  # noqa: PLC0415

        target = scene or bpy.context.scene
        target.render.engine = self.engine
        # Standard, never AgX/Filmic — flat cel colors must survive to the pixel.
        target.view_settings.view_transform = "Standard"
        target.view_settings.look = "None"
        target.view_settings.exposure = 0.0
        target.view_settings.gamma = 1.0
        if self.engine.startswith("BLENDER_EEVEE"):
            target.eevee.taa_render_samples = self.samples
        elif self.engine == "CYCLES":
            target.cycles.samples = self.samples

    def prepare_geometry(self, scene, ctx: LookContext) -> None:
        """Add inverted-hull outlines.

        Outlines live here rather than in the compositor because the cleaner of
        the two analyzed rigs models them as geometry, which keeps the whole
        look renderable with no AOVs, compositor, or addons.
        """
        if self.outline_thickness <= 0.0:
            ctx.data["outlines"] = 0
            return

        import bpy  # noqa: PLC0415

        material = self._outline_material()
        created = 0
        for role in SHADED_ROLES:
            for name in ctx.objects_for(role):
                obj = bpy.data.objects.get(name)
                if obj is None or obj.type != "MESH":
                    continue
                if any(m.name == "Marionette_Outline" for m in obj.modifiers):
                    continue
                mod = obj.modifiers.new("Marionette_Outline", "SOLIDIFY")
                mod.thickness = self.outline_thickness
                mod.offset = 1.0
                mod.use_flip_normals = True
                mod.use_rim = False
                mod.material_offset = len(obj.data.materials)
                obj.data.materials.append(material)
                created += 1
        ctx.data["outlines"] = created

    def build_materials(self, scene, ctx: LookContext) -> None:
        import bpy  # noqa: PLC0415

        built = []
        for role in SHADED_ROLES:
            for name in ctx.objects_for(role):
                obj = bpy.data.objects.get(name)
                if obj is None or obj.type != "MESH" or not obj.data.materials:
                    continue
                for slot, material in enumerate(obj.data.materials):
                    if material is None or material.name == "Marionette_Outline":
                        continue
                    self.apply_to_material(material)
                    built.append(f"{name}[{slot}]:{material.name}")
        ctx.data["materials"] = built

    def build_lighting(self, scene, ctx: LookContext) -> None:
        """A zero-energy sun mirroring the shader's baked light direction."""
        rig = DirectionProxyRig(rotation=self.params.light_direction, energy=0.0)
        lights = rig.apply(scene)
        ctx.data["light_direction"] = self.params.light_direction
        ctx.data["lights"] = [light.obj.name for light in lights]

    # -- shader construction ------------------------------------------------

    def build_graph(self, base_color=(0.8, 0.72, 0.66, 1.0), shadow_color=None) -> NodeGraph:
        """Build the cel shader spec. Pure — no bpy until ``build()``.

        Args:
            base_color: Flat lit color. Both analyzed rigs use tiny (4x4-32x32)
                texture swatches here; a constant is the same thing.
            shadow_color: Flat shadow color. Defaults to a warm shift of the
                base, matching the reddish shadow maps those rigs ship, rather
                than a neutral darkening.
        """
        p: CelParams = self.params
        if shadow_color is None:
            shadow_color = _warm_shadow(base_color)

        g = NodeGraph(OWNER)

        # --- N·L against the baked light direction -------------------------
        geometry = g.node("ShaderNodeNewGeometry", "geometry", location=(-1000, 200))
        light_vec = g.node(
            "ShaderNodeCombineXYZ",
            "light_vec",
            location=(-1000, -40),
            inputs=dict(zip(("X", "Y", "Z"), _direction_vector(p.light_direction))),
        )
        ndotl = g.node(
            "ShaderNodeVectorMath", "ndotl", operation="DOT_PRODUCT", location=(-820, 100)
        )
        g.link(geometry.out("Normal"), ndotl.inp(0))
        g.link(light_vec.out("Vector"), ndotl.inp(1))

        # --- half-lambert: 0.5 * (N·L + push) ------------------------------
        pushed = g.node(
            "ShaderNodeMath", "pushed", operation="ADD", location=(-640, 100),
            inputs={1: p.light_push},
        )
        g.link(ndotl.out("Value"), pushed.inp(0))

        half = g.node(
            "ShaderNodeMath", "half_lambert", operation="MULTIPLY", location=(-460, 100),
            inputs={1: 0.5},
        )
        g.link(pushed.out("Value"), half.inp(0))

        terminator_source = half
        if p.use_vertex_shadow_mask:
            vcol = g.node("ShaderNodeVertexColor", "vertex_mask", location=(-640, -160))
            masked = g.node(
                "ShaderNodeMath", "masked", operation="MULTIPLY", location=(-300, 40)
            )
            g.link(half.out("Value"), masked.inp(0))
            g.link(vcol.out("Color"), masked.inp(1))
            terminator_source = masked

        # --- hard step (or a narrow smooth band) ---------------------------
        if p.shadow_smoothness <= 0.0:
            lit = g.node(
                "ShaderNodeMath", "lit", operation="GREATER_THAN", location=(-120, 100),
                inputs={1: p.shadow_push},
            )
            g.link(terminator_source.out("Value"), lit.inp(0))
        else:
            lit = g.node(
                "ShaderNodeMapRange", "lit", location=(-120, 100), clamp=True,
                inputs={
                    "From Min": p.shadow_push,
                    "From Max": p.shadow_push + p.shadow_smoothness,
                    "To Min": 0.0,
                    "To Max": 1.0,
                },
            )
            g.link(terminator_source.out("Value"), lit.inp("Value"))

        # --- two flat colors, selected -- never blended ---------------------
        bands = g.node(
            "ShaderNodeMix", "bands", data_type="RGBA", blend_type="MIX", location=(120, 100),
            inputs={"A": tuple(shadow_color), "B": tuple(base_color)},
        )
        g.link(lit.out(0), bands.inp("Factor"))

        current = bands.out("Result")

        # --- rim, thresholded on N·V ----------------------------------------
        if p.rim_enabled:
            incoming = g.node("ShaderNodeNewGeometry", "rim_geo", location=(-1000, -420))
            ndotv = g.node(
                "ShaderNodeVectorMath", "ndotv", operation="DOT_PRODUCT", location=(-820, -420)
            )
            g.link(incoming.out("Normal"), ndotv.inp(0))
            g.link(incoming.out("Incoming"), ndotv.inp(1))

            facing = g.node(
                "ShaderNodeMath", "rim_mask", operation="LESS_THAN", location=(-640, -420),
                inputs={1: p.rim_size},
            )
            g.link(ndotv.out("Value"), facing.inp(0))

            scaled = g.node(
                "ShaderNodeMath", "rim_scaled", operation="MULTIPLY", location=(-460, -420),
                inputs={1: p.rim_intensity},
            )
            g.link(facing.out("Value"), scaled.inp(0))

            rim = g.node(
                "ShaderNodeMix", "rim", data_type="RGBA", blend_type="ADD", location=(320, -60),
                inputs={"B": tuple(p.rim_tint) + (1.0,)},
            )
            g.link(scaled.out("Value"), rim.inp("Factor"))
            g.link(current, rim.inp("A"))
            current = rim.out("Result")

        # --- painted detail, multiplied last --------------------------------
        detail = g.node(
            "ShaderNodeMix", "detail", data_type="RGBA", blend_type="MULTIPLY",
            location=(520, 100), inputs={"Factor": 1.0, "B": (1.0, 1.0, 1.0, 1.0)},
        )
        g.link(current, detail.inp("A"))

        # --- emission: the graph is the lighting model ----------------------
        emission = g.node(
            "ShaderNodeEmission", "emission", location=(720, 100), inputs={"Strength": 1.0}
        )
        g.link(detail.out("Result"), emission.inp("Color"))

        output = g.node("ShaderNodeOutputMaterial", "output", adopt=True, location=(900, 100))
        g.link(emission.out("Emission"), output.inp("Surface"))
        return g

    def apply_to_material(self, material) -> None:
        """Rebuild ``material`` as a cel shader, preserving its base color."""
        material.use_nodes = True
        base = _existing_base_color(material)
        # clear_others: this look defines the material's entire surface, so any
        # prior BSDF must go rather than linger disconnected.
        self.build_graph(base_color=base).build(material.node_tree, clear_others=True)
        material.use_backface_culling = True

    def _outline_material(self):
        import bpy  # noqa: PLC0415

        material = bpy.data.materials.get("Marionette_Outline")
        if material is None:
            material = bpy.data.materials.new("Marionette_Outline")
        material.use_nodes = True
        # Backface culling off: the inverted hull is *only* backfaces.
        material.use_backface_culling = False

        g = NodeGraph(OWNER + ".outline")
        emission = g.node(
            "ShaderNodeEmission", "emission", location=(0, 0),
            inputs={"Color": (0.0, 0.0, 0.0, 1.0), "Strength": 1.0},
        )
        output = g.node("ShaderNodeOutputMaterial", "output", adopt=True, location=(200, 0))
        g.link(emission.out("Emission"), output.inp("Surface"))
        g.build(material.node_tree, clear_others=True)
        return material


def _direction_vector(rotation_degrees) -> tuple:
    """Convert an Euler rotation (degrees) to the direction a sun points.

    A Blender sun with zero rotation shines straight down (0, 0, -1); the
    vector the shader needs is the reverse, pointing back toward the light.
    """
    rx, ry, _rz = (math.radians(a) for a in rotation_degrees)
    x = math.sin(ry) * math.cos(rx)
    y = -math.sin(rx)
    z = math.cos(ry) * math.cos(rx)
    length = math.sqrt(x * x + y * y + z * z) or 1.0
    return (x / length, y / length, z / length)


def _warm_shadow(base_color) -> tuple:
    """Derive a shadow hue that is warmer and less bright than ``base_color``.

    Deliberately not a neutral multiply. The reference rigs ship shadow maps
    averaging R > G ≈ B; a flat darkening is the single most common reason a
    cel shader still reads as 3D.
    """
    r, g, b = base_color[:3]
    alpha = base_color[3] if len(base_color) > 3 else 1.0
    return (r * 0.78, g * 0.66, b * 0.70, alpha)


def _existing_base_color(material) -> tuple:
    """Recover a flat base color from whatever the material currently uses."""
    if material.use_nodes and material.node_tree:
        for node in material.node_tree.nodes:
            if node.bl_idname == "ShaderNodeBsdfPrincipled":
                socket = node.inputs.get("Base Color")
                if socket is not None and not socket.links:
                    return tuple(socket.default_value)
    return tuple(material.diffuse_color)
