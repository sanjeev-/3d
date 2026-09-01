"""PBRLook — wraps the conventional render path the library already used.

This look exists to establish the seam. It reproduces what ``Scene.setup_cycles``
and ``Scene.set_hdri`` did, but routed through the Look pipeline, so switching a
project onto looks is a no-op visually.
"""

from typing import Optional

from ..configs import HDRIConfig
from ..rigs import HDRIRig, LightRig, ThreePointRig
from .base import Look, LookContext, LookRequirements
from .params import PBRParams
from .registry import register_look


@register_look("pbr")
class PBRLook(Look):
    """Physically-based rendering with an optional light rig or HDRI."""

    name = "pbr"
    params_model = PBRParams
    requirements = LookRequirements()

    def __init__(
        self,
        params: Optional[PBRParams] = None,
        rig: Optional[LightRig] = None,
        hdri: Optional[HDRIConfig] = None,
    ):
        super().__init__(params)
        if rig is not None and hdri is not None:
            raise ValueError("pass either a light rig or an HDRI, not both")
        self.rig = rig
        self.hdri = hdri

    def configure_render(self, scene, ctx: LookContext) -> None:
        import bpy  # noqa: PLC0415

        target = scene or bpy.context.scene
        p: PBRParams = self.params

        target.render.engine = p.engine
        target.render.resolution_x, target.render.resolution_y = p.resolution
        target.render.film_transparent = p.film_transparent
        target.view_settings.view_transform = p.view_transform

        if p.engine == "CYCLES":
            target.cycles.samples = p.samples
            target.cycles.device = p.device
            target.cycles.use_denoising = p.use_denoising
        elif p.engine.startswith("BLENDER_EEVEE"):
            target.eevee.taa_render_samples = p.samples

    def build_lighting(self, scene, ctx: LookContext) -> None:
        if self.hdri is not None:
            HDRIRig(self.hdri).apply(scene)
            ctx.data["lighting"] = "hdri"
        elif self.rig is not None:
            lights = self.rig.apply(scene)
            ctx.data["lighting"] = self.rig.name
            ctx.data["lights"] = [light.obj.name for light in lights]


@register_look("studio")
class StudioLook(PBRLook):
    """PBR with a three-point rig already attached — a sane default for tests."""

    name = "studio"

    def __init__(self, params: Optional[PBRParams] = None, rig: Optional[LightRig] = None):
        super().__init__(params, rig=rig or ThreePointRig())
