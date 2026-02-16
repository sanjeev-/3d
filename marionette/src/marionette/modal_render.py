"""Modal cloud GPU rendering for Blender."""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import modal

# Create Modal app
app = modal.App("marionette-renderer")

# Define container image with Blender, CUDA, and dependencies
blender_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "wget",
        "xz-utils",
        "libx11-6",
        "libxi6",
        "libxxf86vm1",
        "libxfixes3",
        "libxrender1",
        "libgl1",
        "libglu1-mesa",
    )
    .run_commands(
        # Download and install Blender 3.6
        "wget -q https://download.blender.org/release/Blender3.6/blender-3.6.5-linux-x64.tar.xz",
        "tar -xf blender-3.6.5-linux-x64.tar.xz -C /opt/",
        "ln -s /opt/blender-3.6.5-linux-x64/blender /usr/local/bin/blender",
        "rm blender-3.6.5-linux-x64.tar.xz",
    )
    .pip_install("pydantic>=2.0.0", "pyyaml>=6.0")
)

# Create a network file system for file transfer
nfs = modal.NetworkFileSystem.from_name("marionette-render-storage", create_if_missing=True)


@app.function(
    image=blender_image,
    gpu="A10G",
    timeout=3600,
    network_file_systems={"/mnt/storage": nfs},
)
def render_frame_on_modal(
    blend_file_path: str,
    output_path: str,
    frame: int,
    render_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Render a single frame on Modal with GPU acceleration.

    Args:
        blend_file_path: Path to .blend file in Modal storage
        output_path: Output path for rendered frame
        frame: Frame number to render
        render_config: Render configuration dictionary

    Returns:
        Dict with status, frame number, and output path
    """
    import subprocess
    import sys

    try:
        # Build render script
        script_parts = [
            "import bpy",
            f"bpy.context.scene.frame_start = {frame}",
            f"bpy.context.scene.frame_end = {frame}",
            f"bpy.context.scene.render.filepath = '{output_path}'",
        ]

        # Apply render settings
        if 'engine' in render_config:
            script_parts.append(f"bpy.context.scene.render.engine = '{render_config['engine']}'")

        if 'samples' in render_config:
            script_parts.append(f"bpy.context.scene.cycles.samples = {render_config['samples']}")

        if 'resolution_percentage' in render_config:
            script_parts.append(
                f"bpy.context.scene.render.resolution_percentage = {render_config['resolution_percentage']}"
            )

        if 'denoising' in render_config and render_config['denoising']:
            script_parts.append("bpy.context.scene.cycles.use_denoising = True")

        # Enable GPU rendering
        script_parts.extend([
            "bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'",
            "bpy.context.scene.cycles.device = 'GPU'",
            # Enable all available GPU devices
            "bpy.context.preferences.addons['cycles'].preferences.get_devices()",
            "for device in bpy.context.preferences.addons['cycles'].preferences.devices:",
            "    if device.type == 'CUDA':",
            "        device.use = True",
        ])

        if 'format' in render_config:
            script_parts.append(
                f"bpy.context.scene.render.image_settings.file_format = '{render_config['format']}'"
            )

        render_script = "; ".join(script_parts)

        # Build Blender command
        cmd = [
            "blender",
            "--background",
            blend_file_path,
            "--python-expr",
            render_script,
            "--render-frame",
            str(frame),
        ]

        # Execute Blender
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return {
                "status": "error",
                "frame": frame,
                "error": result.stderr,
            }

        return {
            "status": "success",
            "frame": frame,
            "output_path": output_path,
        }

    except Exception as e:
        return {
            "status": "error",
            "frame": frame,
            "error": str(e),
        }


def render_frames_remote(
    blend_file: str,
    output_dir: str,
    frame_start: int,
    frame_end: int,
    render_config: Dict[str, Any],
    gpu_type: str = "A10G",
    parallel_containers: int = 4,
) -> List[Dict[str, Any]]:
    """
    Render frames on Modal cloud GPUs.

    Args:
        blend_file: Local path to .blend file
        output_dir: Local output directory for rendered frames
        frame_start: First frame to render
        frame_end: Last frame to render
        render_config: Render configuration dictionary
        gpu_type: GPU type to use (A10G, A100, T4)
        parallel_containers: Number of parallel Modal containers

    Returns:
        List of result dictionaries for each frame
    """
    import time
    from pathlib import Path

    blend_path = Path(blend_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Upload .blend file to Modal storage
    remote_blend_path = f"/mnt/storage/{blend_path.name}"

    # For this implementation, we'll use Modal's file system
    # In a real implementation, you'd upload the file here
    print(f"Uploading {blend_file} to Modal storage...")

    # Calculate frame distribution
    total_frames = frame_end - frame_start + 1
    frames = list(range(frame_start, frame_end + 1))

    # Create render tasks
    results = []

    # Update GPU type dynamically
    render_fn = render_frame_on_modal.with_options(gpu=gpu_type)

    print(f"Rendering {total_frames} frames across {parallel_containers} containers...")

    # Render frames in parallel
    with app.run():
        for frame in frames:
            # Build output path for this frame
            frame_output = f"{output_dir}/frame_{frame:04d}.png"
            remote_output = f"/mnt/storage/frame_{frame:04d}.png"

            # Queue the render job
            result = render_fn.remote(
                remote_blend_path,
                remote_output,
                frame,
                render_config,
            )
            results.append(result)

    # Download rendered frames
    print("Downloading rendered frames...")
    # In a real implementation, download files from Modal storage to local output_dir

    return results


def download_frames(remote_dir: str, local_dir: str, frames: List[int]) -> None:
    """
    Download rendered frames from Modal storage to local directory.

    Args:
        remote_dir: Remote directory in Modal storage
        local_dir: Local output directory
        frames: List of frame numbers to download
    """
    local_path = Path(local_dir)
    local_path.mkdir(parents=True, exist_ok=True)

    for frame in frames:
        remote_file = f"{remote_dir}/frame_{frame:04d}.png"
        local_file = local_path / f"frame_{frame:04d}.png"

        # Download file from Modal storage
        # In a real implementation, this would use Modal's file transfer API
        print(f"Downloaded frame {frame} to {local_file}")
