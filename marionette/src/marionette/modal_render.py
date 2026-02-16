"""
Modal cloud GPU rendering module for Blender.

This module provides cloud-based GPU rendering capabilities using Modal.
It sets up a containerized environment with Blender, CUDA drivers, and
distributed frame rendering across parallel Modal containers.

Blend files are stored on a Modal Volume ("marionette-assets") so that
each worker reads directly from cloud storage instead of receiving the
full file bytes in its task tuple.
"""

import modal
import textwrap
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


# Define the Modal app
app = modal.App("marionette-blender-render")

# Shared volume for .blend files and other assets
assets_volume = modal.Volume.from_name("marionette-assets", create_if_missing=True)

# Define the container image with Blender 4.5, CUDA, and Python dependencies
blender_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        # System dependencies
        "wget",
        "xz-utils",
        "libgl1",
        "libglu1-mesa",
        "libsm6",
        "libxi6",
        "libxrender1",
        "libxkbcommon0",
        "libgomp1",
        # CUDA dependencies will be handled by Modal's gpu parameter
    )
    .run_commands(
        # Download and install Blender 4.5.6 (compatible with 4.5.x .blend files)
        "wget -q https://download.blender.org/release/Blender4.5/blender-4.5.6-linux-x64.tar.xz -O /tmp/blender.tar.xz",
        "tar -xf /tmp/blender.tar.xz -C /opt/",
        "mv /opt/blender-4.5* /opt/blender",
        "rm /tmp/blender.tar.xz",
        "ln -s /opt/blender/blender /usr/local/bin/blender",
    )
    .pip_install(
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
    )
)

VOLUME_MOUNT_PATH = "/assets"


class RenderConfig(BaseModel):
    """Configuration for render job."""

    engine: str = Field(default="CYCLES", description="Render engine (CYCLES or EEVEE)")
    device: str = Field(default="GPU", description="Render device (GPU or CPU)")
    samples: int = Field(default=128, description="Number of render samples")
    resolution_percentage: int = Field(default=100, description="Resolution percentage")
    denoising: bool = Field(default=True, description="Enable denoising")
    format: str = Field(default="PNG", description="Output image format")


class FrameRenderTask(BaseModel):
    """Specification for a single frame render task."""

    frame_number: int = Field(description="Frame number to render")
    blend_file_volume_path: str = Field(description="Path to .blend file on the volume")
    output_filename: str = Field(description="Output filename for rendered frame")
    render_config: RenderConfig = Field(default_factory=RenderConfig)


@app.function(
    image=blender_image,
    gpu="A10G",
    timeout=3600,
    retries=2,
    volumes={VOLUME_MOUNT_PATH: assets_volume},
)
def render_single_frame(
    frame_number: int,
    blend_file_volume_path: str,
    output_filename: str,
    render_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Render a single frame using Blender with GPU acceleration.

    This function runs inside a Modal container with GPU access.
    It reads the .blend file directly from the mounted volume,
    configures Blender for GPU rendering via a temp Python script,
    renders the frame, and returns the rendered image data.

    Args:
        frame_number: Frame number to render
        blend_file_volume_path: Path to .blend on the volume (e.g. "models/scenes/bedroom.blend")
        output_filename: Name for the output file
        render_config: Dictionary with render settings

    Returns:
        Dictionary containing:
            - frame_number: The rendered frame number
            - success: Whether rendering succeeded
            - output_data: Rendered image bytes (if successful)
            - error: Error message (if failed)
            - gpu_info: Information about GPU used
    """
    import subprocess
    import tempfile
    from pathlib import Path

    result = {
        "frame_number": frame_number,
        "success": False,
        "output_data": None,
        "error": None,
        "gpu_info": None,
    }

    try:
        # Get GPU information
        try:
            gpu_info_cmd = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if gpu_info_cmd.returncode == 0:
                result["gpu_info"] = gpu_info_cmd.stdout.strip()
            else:
                result["gpu_info"] = "GPU info unavailable"
        except Exception as e:
            result["gpu_info"] = f"GPU detection error: {str(e)}"
            print(f"Warning: Could not detect GPU: {e}")

        # Resolve blend file from the mounted volume
        blend_path = Path(VOLUME_MOUNT_PATH) / blend_file_volume_path
        if not blend_path.exists():
            result["error"] = f"Blend file not found on volume: {blend_path}"
            return result

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            print(f"Rendering frame {frame_number} with {render_config.get('engine', 'CYCLES')}")
            print(f"Blend file: {blend_path}")
            print(f"GPU: {result['gpu_info']}")

            # Build output path — Blender's filepath is a base (no extension);
            # Blender appends the frame number and extension automatically.
            output_path = tmpdir_path / output_filename
            render_filepath = str(tmpdir_path / output_path.stem)

            # Build Blender Python script for render configuration
            script_lines = [
                "import bpy",
                f"bpy.context.scene.frame_set({frame_number})",
                f"bpy.context.scene.render.filepath = '{render_filepath}'",
            ]

            # Apply render settings
            config = render_config

            if config.get('engine'):
                script_lines.append(
                    f"bpy.context.scene.render.engine = '{config['engine']}'"
                )

            if config.get('samples'):
                script_lines.append(
                    f"bpy.context.scene.cycles.samples = {config['samples']}"
                )

            if config.get('resolution_percentage'):
                script_lines.append(
                    f"bpy.context.scene.render.resolution_percentage = {config['resolution_percentage']}"
                )

            if config.get('denoising'):
                script_lines.append(
                    "bpy.context.scene.cycles.use_denoising = True"
                )

            if config.get('format'):
                script_lines.append(
                    f"bpy.context.scene.render.image_settings.file_format = '{config['format']}'"
                )

            # Inject custom per-frame setup script (e.g., camera, focal length)
            if config.get('setup_script'):
                script_lines.append(config['setup_script'])

            # Configure GPU rendering with proper Python (not semicolon-joined)
            if config.get('device') == 'GPU':
                script_lines.append(textwrap.dedent("""\
                    prefs = bpy.context.preferences.addons.get('cycles')
                    if prefs:
                        prefs = prefs.preferences
                        for cdt in ['CUDA', 'OPTIX']:
                            try:
                                prefs.compute_device_type = cdt
                                prefs.get_devices()
                                break
                            except:
                                pass
                        for device in prefs.devices:
                            device.use = True
                    bpy.context.scene.cycles.device = 'GPU'"""))

            # Write the full script to a temp .py file
            script_path = tmpdir_path / "render_setup.py"
            with open(script_path, "w") as f:
                f.write("\n".join(script_lines))

            # Build Blender command using --python (not --python-expr)
            cmd = [
                "blender",
                "--background",
                str(blend_path),
                "--python",
                str(script_path),
                "--render-frame",
                str(frame_number),
            ]

            # Execute Blender render
            print(f"Executing: {' '.join(cmd[:3])}...")
            render_process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3000,
            )

            if render_process.returncode != 0:
                result["error"] = f"Blender process failed with code {render_process.returncode}"
                result["error"] += f"\nSTDOUT: {render_process.stdout[-1000:]}"
                result["error"] += f"\nSTDERR: {render_process.stderr[-1000:]}"
                print(result["error"])
                return result

            # Find the rendered output file.
            # Blender writes to {filepath}{frame:04d}.{ext}, e.g. focal_length_010mm0001.png
            output_file = None
            for candidate in sorted(tmpdir_path.glob(f"{output_path.stem}*")):
                if candidate.suffix in (".png", ".jpg", ".exr", ".tif", ".tiff", ".bmp"):
                    output_file = candidate
                    break

            if not output_file or not output_file.exists():
                dir_contents = list(tmpdir_path.glob("*"))
                result["error"] = f"Output file not found. Expected: {output_path.stem}*. Directory contents: {dir_contents}"
                print(result["error"])
                return result

            # Read rendered frame data
            with open(output_file, "rb") as f:
                result["output_data"] = f.read()

            result["success"] = True
            print(f"Successfully rendered frame {frame_number} ({len(result['output_data'])} bytes)")

    except subprocess.TimeoutExpired:
        result["error"] = f"Render timeout for frame {frame_number}"
        print(result["error"])
    except Exception as e:
        result["error"] = f"Render failed for frame {frame_number}: {str(e)}"
        print(result["error"])
        import traceback
        print(traceback.format_exc())

    return result


def upload_to_volume(local_path: str, volume_path: str, force: bool = False) -> str:
    """
    Upload a local file to the marionette-assets Modal Volume.

    Args:
        local_path: Path to the local file
        volume_path: Destination path on the volume (e.g. "models/scenes/bedroom.blend")
        force: If True, overwrite existing files. If False, skip if already exists.

    Returns:
        The volume_path that was written to
    """
    local = Path(local_path)
    if not local.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    size_mb = local.stat().st_size / (1024 * 1024)

    vol = modal.Volume.from_name("marionette-assets", create_if_missing=True)
    with vol.batch_upload(force=force) as batch:
        batch.put_file(local, volume_path)

    print(f"Uploaded {local.name} ({size_mb:.1f} MB) -> volume:{volume_path}")
    return volume_path


def render_frames_remote(
    blend_file: str,
    frames: List[int],
    output_dir: str,
    render_config: Optional[Dict[str, Any]] = None,
    gpu_type: str = "A10G",
) -> Dict[str, Any]:
    """
    Render multiple frames on Modal cloud infrastructure.

    This function orchestrates the complete remote rendering workflow:
    1. Uploads the .blend file to a Modal Volume (once)
    2. Distributes frames across parallel Modal containers
    3. Each worker reads the .blend from the volume mount (no bytes in task tuples)
    4. Downloads rendered frames back to local output directory

    Args:
        blend_file: Path to the local .blend file
        frames: List of frame numbers to render
        output_dir: Local directory to save rendered frames
        render_config: Render configuration dictionary
        gpu_type: GPU type to use (A10G, A100, etc.)

    Returns:
        Dictionary with render results and statistics
    """
    import time

    blend_path = Path(blend_file)
    if not blend_path.exists():
        return {
            "status": "error",
            "error": f"Blend file not found: {blend_file}",
            "frames_rendered": 0,
        }

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Starting remote render job")
    print(f"Blend file: {blend_file}")
    print(f"Frames: {len(frames)} frames")
    print(f"GPU type: {gpu_type}")
    print(f"Output directory: {output_dir}")

    start_time = time.time()

    # Step 1: Upload blend file to Modal Volume (once, not per-worker)
    volume_path = f"scenes/{blend_path.name}"
    print(f"\n[1/3] Uploading .blend file to Modal Volume...")
    try:
        upload_to_volume(str(blend_path), volume_path, force=True)
        print(f"Uploaded to volume:{volume_path}")
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to upload blend file to volume: {str(e)}",
            "frames_rendered": 0,
        }

    # Prepare default render config
    config = render_config or {}

    # Step 2: Distribute frames across parallel containers and launch render jobs
    print(f"\n[2/3] Distributing {len(frames)} frames across parallel containers...")
    print(f"Launching render jobs on Modal with {gpu_type} GPUs...")

    try:
        # Prepare render tasks — only a path string, not the full file bytes
        render_tasks = [
            (
                frame_num,
                volume_path,
                f"frame_{frame_num:04d}.png",
                config,
            )
            for frame_num in frames
        ]

        # Execute rendering in parallel using Modal's starmap
        with app.run():
            render_fn = render_single_frame
            if gpu_type != "A10G":
                render_fn = modal.Function.from_name(
                    app, "render_single_frame"
                ).with_options(gpu=gpu_type)

            results = list(render_fn.starmap(render_tasks))

        # Analyze results
        successful_frames = [r for r in results if r.get("success")]
        failed_frames = [r for r in results if not r.get("success")]

        print(f"Rendering completed: {len(successful_frames)} successful, {len(failed_frames)} failed")

        if failed_frames:
            print("\nFailed frames:")
            for failed in failed_frames[:5]:
                print(f"  Frame {failed['frame_number']}: {failed.get('error', 'Unknown error')}")
            if len(failed_frames) > 5:
                print(f"  ... and {len(failed_frames) - 5} more")

    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to execute render jobs: {str(e)}",
            "frames_rendered": 0,
        }

    # Step 3: Download rendered frames to local output directory
    print(f"\n[3/3] Downloading rendered frames to {output_dir}...")
    downloaded_files = []

    for result in successful_frames:
        try:
            frame_num = result["frame_number"]
            frame_data = result["output_data"]

            if frame_data:
                output_file = output_path / f"frame_{frame_num:04d}.png"
                with open(output_file, "wb") as f:
                    f.write(frame_data)
                downloaded_files.append(output_file)
        except Exception as e:
            print(f"Warning: Failed to save frame {result.get('frame_number')}: {e}")
            continue

    print(f"Downloaded {len(downloaded_files)} frames")

    # Calculate total time
    total_time = time.time() - start_time

    # Determine final status
    if failed_frames:
        status = "partial_failure" if successful_frames else "error"
    else:
        status = "success"

    print(f"\n{'='*60}")
    print(f"Render completed!")
    print(f"Status: {status}")
    print(f"Successfully rendered: {len(downloaded_files)} frames")
    if failed_frames:
        print(f"Failed frames: {len(failed_frames)}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average time per frame: {total_time/len(frames):.2f}s")
    print(f"Output directory: {output_dir}")
    print(f"{'='*60}\n")

    result_dict = {
        "status": status,
        "frames_rendered": len(downloaded_files),
        "total_time": total_time,
        "output_dir": str(output_dir),
        "downloaded_files": [str(f) for f in downloaded_files],
    }

    if failed_frames:
        result_dict["failed_frames"] = [f["frame_number"] for f in failed_frames]
        result_dict["errors"] = {
            f["frame_number"]: f.get("error", "Unknown error")
            for f in failed_frames
        }

    return result_dict
