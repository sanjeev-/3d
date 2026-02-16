"""
Modal cloud rendering module for Blender projects.

This module provides distributed GPU rendering using Modal's serverless infrastructure.
It handles file uploads, frame distribution across parallel containers, and result downloads.
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import tempfile

try:
    import modal
    MODAL_AVAILABLE = True
except ImportError:
    MODAL_AVAILABLE = False


# Modal app and container image setup (from ticket #1)
if MODAL_AVAILABLE:
    # Create Modal app
    app = modal.App("marionette-blender-render")

    # Define container image with Blender 3.6+, CUDA, and Python dependencies
    blender_image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install(
            "wget",
            "xz-utils",
            "libxi6",
            "libxrender1",
            "libxkbcommon0",
            "libgl1",
            "libglu1-mesa",
        )
        .run_commands(
            # Download and install Blender 3.6
            "wget -q https://download.blender.org/release/Blender3.6/blender-3.6.5-linux-x64.tar.xz -O /tmp/blender.tar.xz",
            "tar -xf /tmp/blender.tar.xz -C /opt",
            "ln -s /opt/blender-3.6.5-linux-x64/blender /usr/local/bin/blender",
            "rm /tmp/blender.tar.xz"
        )
        .pip_install("pydantic")
    )

    # Create Modal Volume for file storage
    blend_files_volume = modal.Volume.from_name("marionette-blend-files", create_if_missing=True)
    render_output_volume = modal.Volume.from_name("marionette-render-output", create_if_missing=True)


def _split_frame_range(frame_start: int, frame_end: int, num_containers: int) -> List[Tuple[int, int]]:
    """
    Split a frame range evenly across N containers.

    Args:
        frame_start: First frame to render
        frame_end: Last frame to render (inclusive)
        num_containers: Number of parallel containers

    Returns:
        List of (start, end) tuples for each container
    """
    total_frames = frame_end - frame_start + 1
    frames_per_container = max(1, total_frames // num_containers)

    ranges = []
    current_start = frame_start

    for i in range(num_containers):
        if i == num_containers - 1:
            # Last container gets any remaining frames
            current_end = frame_end
        else:
            current_end = min(current_start + frames_per_container - 1, frame_end)

        if current_start <= frame_end:
            ranges.append((current_start, current_end))
            current_start = current_end + 1

    return ranges


def _upload_blend_file(blend_file_path: str, job_id: str) -> str:
    """
    Upload .blend file to Modal Volume.

    Args:
        blend_file_path: Local path to .blend file
        job_id: Unique job identifier

    Returns:
        Remote path to uploaded file in Modal Volume
    """
    if not MODAL_AVAILABLE:
        raise ImportError("Modal is not installed. Install it with: pip install modal")

    blend_path = Path(blend_file_path)
    if not blend_path.exists():
        raise FileNotFoundError(f"Blend file not found: {blend_file_path}")

    # Remote path in Modal Volume
    remote_blend_path = f"/blend_files/{job_id}/{blend_path.name}"

    # Upload file to Modal Volume
    with blend_files_volume.batch_upload() as batch:
        batch.put_file(str(blend_path), remote_blend_path)

    return remote_blend_path


def download_frames(job_id: str, local_output_dir: str, frame_start: int, frame_end: int) -> List[Path]:
    """
    Download rendered frames from Modal Volume to local directory.

    Args:
        job_id: Unique job identifier
        local_output_dir: Local directory to save frames
        frame_start: First frame number
        frame_end: Last frame number

    Returns:
        List of paths to downloaded frame files
    """
    if not MODAL_AVAILABLE:
        raise ImportError("Modal is not installed. Install it with: pip install modal")

    output_path = Path(local_output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded_files = []

    # Download each frame from Modal Volume
    for frame_num in range(frame_start, frame_end + 1):
        # Assuming PNG format with frame number padding
        remote_frame_path = f"/render_output/{job_id}/frame_{frame_num:04d}.png"
        local_frame_path = output_path / f"frame_{frame_num:04d}.png"

        try:
            # Download file from Modal Volume
            with render_output_volume.batch_download() as batch:
                frame_data = batch.get_file(remote_frame_path)

            # Write to local file
            local_frame_path.write_bytes(frame_data)
            downloaded_files.append(local_frame_path)

        except Exception as e:
            print(f"Warning: Failed to download frame {frame_num}: {e}")
            continue

    return downloaded_files


if MODAL_AVAILABLE:
    @app.function(
        image=blender_image,
        gpu="A10G",
        volumes={
            "/blend_files": blend_files_volume,
            "/render_output": render_output_volume,
        },
        timeout=3600,  # 1 hour timeout
    )
    def render_frames_on_modal(
        job_id: str,
        remote_blend_path: str,
        frame_start: int,
        frame_end: int,
        render_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Render frames using Blender on Modal container with GPU.

        This function runs inside a Modal container and handles the actual rendering.

        Args:
            job_id: Unique job identifier
            remote_blend_path: Path to .blend file in Modal Volume
            frame_start: First frame to render
            frame_end: Last frame to render
            render_config: Render settings (samples, resolution, etc.)

        Returns:
            Dictionary with render status and metadata
        """
        import subprocess
        import json

        config = render_config or {}

        # Prepare output directory in Modal Volume
        output_dir = f"/render_output/{job_id}"
        os.makedirs(output_dir, exist_ok=True)

        # Build Blender Python script for render configuration
        render_script_parts = [
            "import bpy",
            f"bpy.context.scene.frame_start = {frame_start}",
            f"bpy.context.scene.frame_end = {frame_end}",
            f"bpy.context.scene.render.filepath = '{output_dir}/frame_'",
        ]

        # Apply render configuration
        if config.get('engine'):
            render_script_parts.append(f"bpy.context.scene.render.engine = '{config['engine']}'")
        else:
            render_script_parts.append("bpy.context.scene.render.engine = 'CYCLES'")

        if config.get('samples'):
            render_script_parts.append(f"bpy.context.scene.cycles.samples = {config['samples']}")

        if config.get('resolution_percentage'):
            render_script_parts.append(
                f"bpy.context.scene.render.resolution_percentage = {config['resolution_percentage']}"
            )

        if config.get('denoising', True):
            render_script_parts.append("bpy.context.scene.cycles.use_denoising = True")

        # Enable GPU rendering with CUDA
        render_script_parts.extend([
            "import bpy",
            "prefs = bpy.context.preferences.addons['cycles'].preferences",
            "prefs.compute_device_type = 'CUDA'",
            "prefs.get_devices()",
            "for device in prefs.devices:",
            "    if device.type == 'CUDA':",
            "        device.use = True",
            "bpy.context.scene.cycles.device = 'GPU'",
        ])

        if config.get('format', 'PNG'):
            render_script_parts.append(
                f"bpy.context.scene.render.image_settings.file_format = '{config.get('format', 'PNG')}'"
            )

        render_script = "; ".join(render_script_parts)

        # Build Blender command
        cmd = [
            "blender",
            "--background",
            remote_blend_path,
            "--python-expr",
            render_script,
            "--render-anim",
        ]

        try:
            # Run Blender rendering
            print(f"Starting render for frames {frame_start}-{frame_end}...")
            print(f"Command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            print(f"Render completed successfully for frames {frame_start}-{frame_end}")

            # Commit changes to Volume
            render_output_volume.commit()

            return {
                "status": "success",
                "frames_rendered": frame_end - frame_start + 1,
                "frame_start": frame_start,
                "frame_end": frame_end,
                "job_id": job_id,
                "output_dir": output_dir,
            }

        except subprocess.CalledProcessError as e:
            error_msg = f"Blender rendering failed: {e.stderr}"
            print(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "frame_start": frame_start,
                "frame_end": frame_end,
                "job_id": job_id,
            }
        except Exception as e:
            error_msg = f"Unexpected error during rendering: {str(e)}"
            print(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "frame_start": frame_start,
                "frame_end": frame_end,
                "job_id": job_id,
            }


def render_frames_remote(
    blend_file: str,
    output_dir: str,
    frame_start: int,
    frame_end: int,
    render_config: Optional[Dict[str, Any]] = None,
    num_containers: int = 4,
    gpu_type: str = "A10G",
) -> Dict[str, Any]:
    """
    Render frames remotely using Modal cloud GPU containers.

    This function orchestrates the entire remote rendering process:
    1. Uploads the .blend file to Modal Volume
    2. Splits frame range across parallel containers
    3. Launches rendering jobs on Modal
    4. Downloads rendered frames back to local output directory

    Args:
        blend_file: Path to local .blend file
        output_dir: Local directory to save rendered frames
        frame_start: First frame to render
        frame_end: Last frame to render
        render_config: Render settings (samples, resolution, denoising, etc.)
        num_containers: Number of parallel Modal containers to use
        gpu_type: GPU type to use (A10G, A100, etc.)

    Returns:
        Dictionary with render status, timing, and output information
    """
    if not MODAL_AVAILABLE:
        raise ImportError(
            "Modal is not installed. Install it with: pip install modal\n"
            "Then authenticate with: modal token new"
        )

    import time
    import uuid

    # Generate unique job ID
    job_id = f"render_{uuid.uuid4().hex[:8]}_{int(time.time())}"

    print(f"Starting remote render job: {job_id}")
    print(f"Blend file: {blend_file}")
    print(f"Frame range: {frame_start}-{frame_end}")
    print(f"Containers: {num_containers}")
    print(f"GPU type: {gpu_type}")

    start_time = time.time()

    # Step 1: Upload blend file to Modal Volume
    print("\n[1/3] Uploading .blend file to Modal...")
    try:
        remote_blend_path = _upload_blend_file(blend_file, job_id)
        print(f"✓ Uploaded to: {remote_blend_path}")
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to upload blend file: {str(e)}",
            "job_id": job_id,
        }

    # Step 2: Split frame range and launch parallel rendering jobs
    print(f"\n[2/3] Distributing frames across {num_containers} containers...")
    frame_ranges = _split_frame_range(frame_start, frame_end, num_containers)

    print("Frame distribution:")
    for i, (start, end) in enumerate(frame_ranges, 1):
        print(f"  Container {i}: frames {start}-{end} ({end - start + 1} frames)")

    # Launch parallel rendering jobs using Modal's map functionality
    print("\nLaunching render jobs on Modal...")

    try:
        with app.run():
            # Create list of arguments for each container
            render_jobs = [
                {
                    "job_id": job_id,
                    "remote_blend_path": remote_blend_path,
                    "frame_start": start,
                    "frame_end": end,
                    "render_config": render_config,
                }
                for start, end in frame_ranges
            ]

            # Run rendering jobs in parallel using starmap
            results = list(
                render_frames_on_modal.starmap(
                    [(job["job_id"], job["remote_blend_path"], job["frame_start"],
                      job["frame_end"], job["render_config"])
                     for job in render_jobs]
                )
            )

        # Check results
        failed_jobs = [r for r in results if r.get("status") == "error"]
        if failed_jobs:
            error_messages = [r.get("error", "Unknown error") for r in failed_jobs]
            return {
                "status": "partial_failure",
                "error": f"Some render jobs failed: {'; '.join(error_messages)}",
                "successful_jobs": len(results) - len(failed_jobs),
                "failed_jobs": len(failed_jobs),
                "job_id": job_id,
            }

        print(f"✓ All {len(results)} render jobs completed successfully")

    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to execute render jobs: {str(e)}",
            "job_id": job_id,
        }

    # Step 3: Download rendered frames from Modal to local output directory
    print(f"\n[3/3] Downloading rendered frames to {output_dir}...")
    try:
        downloaded_files = download_frames(job_id, output_dir, frame_start, frame_end)
        print(f"✓ Downloaded {len(downloaded_files)} frames")
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to download frames: {str(e)}",
            "job_id": job_id,
        }

    # Calculate total time
    total_time = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"Render completed successfully!")
    print(f"Job ID: {job_id}")
    print(f"Total frames: {len(downloaded_files)}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Output directory: {output_dir}")
    print(f"{'='*60}\n")

    return {
        "status": "success",
        "job_id": job_id,
        "frames_rendered": len(downloaded_files),
        "total_time": total_time,
        "output_dir": output_dir,
        "downloaded_files": [str(f) for f in downloaded_files],
    }
