"""Parameter models for looks.

Structure and parameters are separated deliberately. Two visually distinct anime
rigs analyzed for this library share the *same* 68-node shader group and differ
only in about a dozen scalars, which texture slots are bound, and which
auxiliary geometry exists. That is the whole argument for pydantic params:
art direction becomes YAML, not code edits.
"""

from typing import Optional, Tuple

from pydantic import BaseModel, Field

RGB = Tuple[float, float, float]


class CelParams(BaseModel):
    """Cel / anime shading parameters.

    Defaults are the Zenitsu ("zen") configuration, which is the cleaner and
    more portable of the two rigs analyzed: purely geometric half-lambert with
    no painted offset maps, specular disabled, flat base colors, subtle rims,
    and hand-drawn detail applied as a multiply overlay. It also needs no
    addons, AOVs, or compositor to render correctly.

    Contrast with ``bridget_preset()``, which drives the same math from painted
    ILM/vertex data and enables a gated specular.
    """

    # -- shading terminator -------------------------------------------------
    light_push: float = Field(
        default=1.0,
        description="Added to N·L before halving. 1.0 yields exact half-lambert.",
    )
    shadow_push: float = Field(
        default=0.5,
        description="Threshold on the modified N·L. 0.5 puts the terminator at the geometric horizon.",
    )
    shadow_smoothness: float = Field(
        default=0.0,
        ge=0.0,
        description="0.0 selects a hard step (cel). Above 0 fades the edge.",
    )
    shadow_vertex_threshold: float = Field(
        default=0.5, description="Vertex-red must exceed this for a surface to be lit."
    )

    # -- second shadow band -------------------------------------------------
    shadow2_push: float = Field(
        default=-1.0, description="-1.0 disables the second (deepest) shadow band."
    )
    shadow2_smoothness: float = Field(default=0.0, ge=0.0)
    shadow2_vertex_threshold: float = Field(default=0.1)
    permanent_shadow_threshold: float = Field(
        default=0.2, description="Regions below this in the offset map stay shadowed always."
    )

    # -- specular -----------------------------------------------------------
    specular_size: float = Field(
        default=0.0,
        description="0.0 disables specular entirely (threshold becomes unreachable).",
    )
    specular_intensity: float = Field(default=1.0)
    specular_tint: RGB = Field(default=(1.0, 1.0, 1.0))

    # -- rim lights ---------------------------------------------------------
    rim_size: float = Field(default=0.2, description="-1.0 disables the highlight rim.")
    rim_intensity: float = Field(default=0.1, description="Zen keeps this very low.")
    rim_tint: RGB = Field(default=(1.0, 1.0, 1.0))
    shadow_rim_size: float = Field(default=0.2, description="-1.0 disables the shadow rim.")
    shadow_rim_intensity: float = Field(default=0.1)
    shadow_rim_tint: RGB = Field(default=(1.0, 1.0, 1.0))

    # -- per-band color -----------------------------------------------------
    base_tint: RGB = Field(default=(1.0, 1.0, 1.0))
    base_intensity: float = Field(default=1.0)
    shadow_tint: RGB = Field(default=(1.0, 1.0, 1.0))
    shadow_intensity: float = Field(default=1.0)

    # -- control-data bindings ----------------------------------------------
    use_offset_map: bool = Field(
        default=False,
        description="Bind a painted ILM/offset texture. False feeds a neutral 0.5 constant, "
        "making the shadow line purely geometric.",
    )
    use_vertex_shadow_mask: bool = Field(
        default=False, description="Honor painted vertex colors as a shadow mask."
    )

    # -- light direction ----------------------------------------------------
    light_direction: Tuple[float, float, float] = Field(
        default=(45.0, -35.0, 0.0),
        description="Euler degrees. Mirrored onto a proxy sun so artists can grab it.",
    )

    def as_shader_inputs(self) -> dict:
        """Map params onto the Arc System Works group's socket names.

        Kept here so the naming lives in one place when the shader graph lands.
        """
        return {
            "Global Light Push": self.light_push,
            "Shadow 1 Push": self.shadow_push,
            "Shadow 1 Smoothness": self.shadow_smoothness,
            "Shadow 1 Vertex Threshold": self.shadow_vertex_threshold,
            "Shadow 2 Push": self.shadow2_push,
            "Shadow 2 Smoothness": self.shadow2_smoothness,
            "Shadow 2 Vertex Threshold": self.shadow2_vertex_threshold,
            "Permanent Shadow Threshold": self.permanent_shadow_threshold,
            "Specular Size": self.specular_size,
            "Specular Intensity": self.specular_intensity,
            "Highlight Rimlight Size": self.rim_size,
            "Highlight Rimlight Intensity": self.rim_intensity,
            "Shadow Rimlight Size": self.shadow_rim_size,
            "Shadow Rimlight Intensity": self.shadow_rim_intensity,
            "Base Intensity": self.base_intensity,
            "Shadow 1 Intensity": self.shadow_intensity,
        }

    @property
    def specular_enabled(self) -> bool:
        """Specular thresholds on ``1 - specular_size``; at 0.0 it never passes."""
        return self.specular_size > 0.0

    @property
    def rim_enabled(self) -> bool:
        return self.rim_size >= 0.0


def zen_preset() -> CelParams:
    """The default: flat, hard-edged, geometric. Renders with no dependencies."""
    return CelParams()


def bridget_preset() -> CelParams:
    """Painted-control-data variant: offset maps, vertex masks, gated specular."""
    return CelParams(
        shadow_vertex_threshold=0.0,
        shadow2_vertex_threshold=0.0,
        permanent_shadow_threshold=-1.0,
        specular_size=0.2,
        rim_size=-1.0,
        rim_intensity=1.0,
        shadow_rim_size=-1.0,
        shadow_rim_intensity=0.5,
        use_offset_map=True,
        use_vertex_shadow_mask=True,
        light_direction=(53.46, -27.73, 50.65),
    )


class PBRParams(BaseModel):
    """Conventional physically-based rendering settings."""

    engine: str = Field(default="CYCLES")
    samples: int = Field(default=128, ge=1)
    resolution: Tuple[int, int] = Field(default=(1920, 1080))
    view_transform: str = Field(default="AgX")
    device: str = Field(default="GPU")
    use_denoising: bool = Field(default=True)
    film_transparent: bool = Field(default=False)
