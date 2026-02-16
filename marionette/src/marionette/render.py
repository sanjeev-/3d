<<<<<<< HEAD
import bpy
import os
import sys
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, Field
from tqdm import tqdm

class RenderEngine(str, Enum):
    CYCLES = "CYCLES"
    BLENDER_EEVEE = "BLENDER_EEVEE"
    BLENDER_EEVEE_NEXT = "BLENDER_EEVEE_NEXT"

class FileFormat(str, Enum):
    PNG = "PNG"
    JPEG = "JPEG"
    OPEN_EXR = "OPEN_EXR"
    FFMPEG = "FFMPEG"

class VideoCodec(str, Enum):
    H264 = "H264"
    DNXHD = "DNXHD"
    WEBM = "WEBM"

class RenderConfig(BaseModel):
    """Blueprint for render settings"""
    output_dir: str = "renders/output"
    engine: RenderEngine = RenderEngine.CYCLES
    samples: int = Field(default=128, ge=1)
    resolution: Tuple[int, int] = (512, 512)
    file_format: FileFormat = FileFormat.PNG
    filename_pattern: str = "render_{frame:04d}"
    use_motion_blur: bool = True
    use_gpu: bool = True
    transparent_bg: bool = False
    video_container: str = "MPEG4"  # Only used when file_format is FFMPEG
    video_codec: VideoCodec = VideoCodec.H264  # Only used when file_format is FFMPEG

class SilenceBlender:
    """Context manager to suppress Blender's noisy stdout/stderr."""
    def __enter__(self):
        self.old_stdout_fd = os.dup(1)
        self.old_stderr_fd = os.dup(2)
        self.devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.devnull_fd, 1)
        os.dup2(self.devnull_fd, 2)

    def __exit__(self, type, value, traceback):
        os.dup2(self.old_stdout_fd, 1)
        os.dup2(self.old_stderr_fd, 2)
        os.close(self.old_stdout_fd)
        os.close(self.old_stderr_fd)
        os.close(self.devnull_fd)

class Renderer:
    """The high-level interface to trigger renders."""
    def __init__(self, scene_wrapper):
        self.sw = scene_wrapper
        self.scene = scene_wrapper.scene

    def apply_config(self, config: RenderConfig):
        """Applies RenderConfig settings to the Blender scene."""
        s = self.scene
        render = s.render
        
        render.engine = config.engine.value
        render.resolution_x = config.resolution[0]
        render.resolution_y = config.resolution[1]
        render.image_settings.file_format = config.file_format.value
        render.use_motion_blur = config.use_motion_blur
        s.render.film_transparent = config.transparent_bg

        if config.engine == RenderEngine.CYCLES:
            s.cycles.samples = config.samples
            if config.use_gpu:
                s.cycles.device = 'GPU'
                # Setup Metal for Mac
                prefs = bpy.context.preferences.addons['cycles'].preferences
                prefs.compute_device_type = 'METAL'
                for d in prefs.get_devices_for_type('METAL'):
                    d.use = True
            else:
                s.cycles.device = 'CPU'

        if not os.path.exists(config.output_dir):
            os.makedirs(config.output_dir)

        if config.file_format == FileFormat.FFMPEG:
            # Configure FFmpeg settings
            render.ffmpeg.format = config.video_container
            render.ffmpeg.codec = config.video_codec.value
            render.ffmpeg.constant_rate_factor = 'MEDIUM' # Quality
            render.ffmpeg.audio_codec = 'NONE'
        
        self.config = config

    def render_frame(self, frame: int):
            """Renders a single frame after updating the scene's timeline."""
            self.sw.current_frame = frame
            filename = self.config.filename_pattern.format(frame=frame)
            
            if self.config.file_format == FileFormat.PNG:
                ext = "png"
            elif self.config.file_format == FileFormat.JPEG:
                ext = "jpg"
            elif self.config.file_format == FileFormat.OPEN_EXR:
                ext = "exr"
            else:
                ext = "png"
                
            filepath = os.path.abspath(os.path.join(self.config.output_dir, f"{filename}.{ext}"))
            self.scene.render.filepath = filepath
            with SilenceBlender():
                bpy.ops.render.render(write_still=True)
                    
            return filepath

    def render_sequence(self, start: Optional[int] = None, end: Optional[int] = None):
        """Renders a range of frames with a tqdm progress bar."""
        start_frame = start or self.scene.frame_start
        end_frame = end or self.scene.frame_end
        total_frames = end_frame - start_frame + 1

        print(f"🚀 Rendering {total_frames} frames to: {self.config.output_dir}")
        
        pbar = tqdm(total=total_frames, desc="Rendering", unit="frame")
        
        for frame in range(start_frame, end_frame + 1):
            self.render_frame(frame)
            pbar.update(1)
            
        pbar.close()
        print(f"🏁 Sequence complete.")
=======
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
>>>>>>> de43dd6b8f02cc9b1162c13085a06f0dd97a3346
