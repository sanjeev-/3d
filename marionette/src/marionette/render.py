"""
Rendering utilities for Blender projects with Modal cloud GPU support.
"""

import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import yaml


class RenderConfig(BaseModel):
    """Configuration for rendering operations."""

    blend_file: str = Field(..., description="Path to .blend file")
    output_dir: str = Field(..., description="Output directory for rendered frames")
    frame_start: int = Field(..., description="First frame to render")
    frame_end: int = Field(..., description="Last frame to render")
    use_modal: bool = Field(default=False, description="Use Modal cloud rendering")
    gpu_type: Optional[str] = Field(
        default=None, description="GPU type for Modal (A10G, A100, T4)"
    )
    parallel_containers: Optional[int] = Field(
        default=4, description="Number of parallel Modal containers"
    )
    render_settings: Dict[str, Any] = Field(
        default_factory=dict, description="Render settings (samples, resolution, etc.)"
    )
    blender_executable: str = Field(default="blender", description="Path to Blender executable")

    @field_validator("gpu_type")
    @classmethod
    def validate_gpu_type(cls, v, info):
        """Validate that gpu_type is only set when use_modal is True."""
        if v is not None:
            # Check if use_modal is True
            use_modal = info.data.get("use_modal", False)
            if not use_modal:
                raise ValueError("gpu_type can only be specified when use_modal=True")
            if v not in ["A10G", "A100", "T4"]:
                raise ValueError(f"Invalid gpu_type: {v}. Must be one of: A10G, A100, T4")
        return v

    @field_validator("parallel_containers")
    @classmethod
    def validate_parallel_containers(cls, v, info):
        """Validate that parallel_containers is only set when use_modal is True."""
        if v is not None and v != 4:  # 4 is the default
            use_modal = info.data.get("use_modal", False)
            if not use_modal:
                raise ValueError(
                    "parallel_containers can only be specified when use_modal=True"
                )
        return v

    @field_validator("blend_file")
    @classmethod
    def validate_blend_file(cls, v):
        """Validate that blend file exists."""
        if not Path(v).exists():
            raise ValueError(f"Blend file not found: {v}")
        return v


class Renderer:
    """
    Handles rendering of Blender scenes locally or on Modal cloud GPUs.

    Provides methods to render single frames, frame ranges, or entire movies
    using Blender's command-line interface or Modal's distributed GPU infrastructure.
    """

    def __init__(self, blender_executable: str = "blender"):
        """
        Initialize the renderer.

        Args:
            blender_executable: Path to Blender executable (default: "blender")
        """
        self.blender_executable = blender_executable

    def render_sequence(self, config: RenderConfig) -> list:
        """
        Render a sequence of frames using either local or Modal backend.

        Args:
            config: RenderConfig object with all rendering parameters

        Returns:
            List of results (return codes for local, status dicts for Modal)
        """
        if config.use_modal:
            return self._render_modal(config)
        else:
            return self._render_local(config)

    def _render_local(self, config: RenderConfig) -> list:
        """
        Render frames locally using Blender.

        Args:
            config: RenderConfig object

        Returns:
            List with single return code from Blender process
        """
        blend_path = Path(config.blend_file)
        output_path = Path(config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Build output path pattern for frames
        output_pattern = str(output_path / "frame_####.png")

        # Build Blender command
        cmd = [config.blender_executable, "--background", str(blend_path)]

        # Add render script
        render_script = self._build_render_script(
            output_pattern,
            config.frame_start,
            config.frame_end,
            config.render_settings,
        )

        cmd.extend(["--python-expr", render_script, "--render-anim"])

        # Execute Blender
        print(
            f"Rendering {blend_path.name} frames {config.frame_start}-{config.frame_end}..."
        )
        result = subprocess.run(cmd, capture_output=False)

        return [result.returncode]

    def _render_modal(self, config: RenderConfig) -> list:
        """
        Render frames on Modal cloud GPUs.

        Args:
            config: RenderConfig object

        Returns:
            List of result dictionaries from Modal
        """
        from . import modal_render

        results = modal_render.render_frames_remote(
            blend_file=config.blend_file,
            output_dir=config.output_dir,
            frame_start=config.frame_start,
            frame_end=config.frame_end,
            render_config=config.render_settings,
            gpu_type=config.gpu_type or "A10G",
            parallel_containers=config.parallel_containers or 4,
        )

        return results

    def render_scene(
        self,
        blend_file: str,
        output_path: str,
        frame_start: int,
        frame_end: int,
        render_config: Optional[Dict[str, Any]] = None,
        background: bool = True,
    ) -> int:
        """
        Render a scene from a Blender file (legacy method for backward compatibility).

        Args:
            blend_file: Path to .blend file
            output_path: Output path for rendered frames
            frame_start: First frame to render
            frame_end: Last frame to render
            render_config: Render settings override
            background: Run Blender in background mode

        Returns:
            Return code from Blender process
        """
        blend_path = Path(blend_file)
        if not blend_path.exists():
            raise FileNotFoundError(f"Blend file not found: {blend_path}")

        # Build Blender command
        cmd = [self.blender_executable]

        if background:
            cmd.append("--background")

        cmd.extend([
            str(blend_path),
            "--python-expr",
            self._build_render_script(
                output_path, frame_start, frame_end, render_config
            ),
            "--render-anim",
        ])

        # Execute Blender
        print(f"Rendering {blend_path.name} frames {frame_start}-{frame_end}...")
        result = subprocess.run(cmd, capture_output=False)

        return result.returncode

    def render_frame(
        self,
        blend_file: str,
        output_path: str,
        frame: int,
        render_config: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Render a single frame (legacy method for backward compatibility).

        Args:
            blend_file: Path to .blend file
            output_path: Output path for rendered frame
            frame: Frame number to render
            render_config: Render settings override

        Returns:
            Return code from Blender process
        """
        return self.render_scene(blend_file, output_path, frame, frame, render_config)

    def _build_render_script(
        self,
        output_path: str,
        frame_start: int,
        frame_end: int,
        render_config: Optional[Dict[str, Any]],
    ) -> str:
        """
        Build Python script to configure Blender render settings.

        Args:
            output_path: Output path for renders
            frame_start: First frame
            frame_end: Last frame
            render_config: Render configuration dict

        Returns:
            Python code as string
        """
        config = render_config or {}

        script_parts = [
            "import bpy",
            f"bpy.context.scene.frame_start = {frame_start}",
            f"bpy.context.scene.frame_end = {frame_end}",
            f"bpy.context.scene.render.filepath = '{output_path}'",
        ]

        # Apply render settings
        if "engine" in config:
            script_parts.append(
                f"bpy.context.scene.render.engine = '{config['engine']}'"
            )

        if "samples" in config:
            script_parts.append(
                f"bpy.context.scene.cycles.samples = {config['samples']}"
            )

        if "resolution_percentage" in config:
            script_parts.append(
                f"bpy.context.scene.render.resolution_percentage = {config['resolution_percentage']}"
            )

        if "denoising" in config and config["denoising"]:
            script_parts.append("bpy.context.scene.cycles.use_denoising = True")

        if "device" in config and config["device"] == "GPU":
            script_parts.extend([
                "bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'",
                "bpy.context.scene.cycles.device = 'GPU'",
            ])

        if "format" in config:
            script_parts.append(
                f"bpy.context.scene.render.image_settings.file_format = '{config['format']}'"
            )

        return "; ".join(script_parts)

    def load_render_preset(self, preset_file: str, preset_name: str) -> Dict[str, Any]:
        """
        Load a render preset from a YAML file.

        Args:
            preset_file: Path to preset YAML file
            preset_name: Name of the preset to load

        Returns:
            Render configuration dict
        """
        with open(preset_file, "r") as f:
            presets = yaml.safe_load(f)

        if preset_name not in presets.get("presets", {}):
            raise ValueError(f"Preset '{preset_name}' not found in {preset_file}")

        return presets["presets"][preset_name]
