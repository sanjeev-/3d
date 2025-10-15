"""
Rendering utilities for Blender projects.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import yaml


class Renderer:
    """
    Handles rendering of Blender scenes.

    Provides methods to render single frames, frame ranges, or entire movies
    using Blender's command-line interface.
    """

    def __init__(self, blender_executable: str = "blender"):
        """
        Initialize the renderer.

        Args:
            blender_executable: Path to Blender executable (default: "blender")
        """
        self.blender_executable = blender_executable

    def render_scene(self, blend_file: str, output_path: str,
                    frame_start: int, frame_end: int,
                    render_config: Optional[Dict[str, Any]] = None,
                    background: bool = True) -> int:
        """
        Render a scene from a Blender file.

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
            self._build_render_script(output_path, frame_start, frame_end, render_config),
            "--render-anim"
        ])

        # Execute Blender
        print(f"Rendering {blend_path.name} frames {frame_start}-{frame_end}...")
        result = subprocess.run(cmd, capture_output=False)

        return result.returncode

    def render_frame(self, blend_file: str, output_path: str, frame: int,
                    render_config: Optional[Dict[str, Any]] = None) -> int:
        """
        Render a single frame.

        Args:
            blend_file: Path to .blend file
            output_path: Output path for rendered frame
            frame: Frame number to render
            render_config: Render settings override

        Returns:
            Return code from Blender process
        """
        return self.render_scene(blend_file, output_path, frame, frame, render_config)

    def _build_render_script(self, output_path: str, frame_start: int,
                            frame_end: int, render_config: Optional[Dict[str, Any]]) -> str:
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
        if 'engine' in config:
            script_parts.append(f"bpy.context.scene.render.engine = '{config['engine']}'")

        if 'samples' in config:
            script_parts.append(f"bpy.context.scene.cycles.samples = {config['samples']}")

        if 'resolution_percentage' in config:
            script_parts.append(
                f"bpy.context.scene.render.resolution_percentage = {config['resolution_percentage']}"
            )

        if 'denoising' in config and config['denoising']:
            script_parts.append("bpy.context.scene.cycles.use_denoising = True")

        if 'device' in config and config['device'] == 'GPU':
            script_parts.extend([
                "bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'",
                "bpy.context.scene.cycles.device = 'GPU'"
            ])

        if 'format' in config:
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
        with open(preset_file, 'r') as f:
            presets = yaml.safe_load(f)

        if preset_name not in presets.get('presets', {}):
            raise ValueError(f"Preset '{preset_name}' not found in {preset_file}")

        return presets['presets'][preset_name]
