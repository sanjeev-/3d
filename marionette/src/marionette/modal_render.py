"""
Modal cloud GPU rendering module for Blender.

This module provides cloud-based GPU rendering capabilities using Modal.
It sets up a containerized environment with Blender, CUDA drivers, and
distributed frame rendering across parallel Modal containers.
"""

import modal
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


# Define the Modal app
app = modal.App("marionette-blender-render")


# Define the container image with Blender 3.6+, CUDA, and Python dependencies
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
        # Download and install Blender 3.6 LTS
        "wget -q https://download.blender.org/release/Blender3.6/blender-3.6.9-linux-x64.tar.xz -O /tmp/blender.tar.xz",
        "tar -xf /tmp/blender.tar.xz -C /opt/",
        "mv /opt/blender-3.6.9-linux-x64 /opt/blender",
        "rm /tmp/blender.tar.xz",
        "ln -s /opt/blender/blender /usr/local/bin/blender",
    )
    .pip_install(
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
    )
)


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
    blend_file_data: bytes = Field(description="Blender file contents")
    output_filename: str = Field(description="Output filename for rendered frame")
    render_config: RenderConfig = Field(default_factory=RenderConfig)


@app.function(
    image=blender_image,
    gpu="A10G",  # Default GPU type (can be overridden)
    timeout=3600,  # 1 hour timeout per frame
    retries=2,  # Retry failed renders
)
def render_single_frame(
    frame_number: int,
    blend_file_data: bytes,
    output_filename: str,
    render_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Render a single frame using Blender with GPU acceleration.

    This function runs inside a Modal container with GPU access.
    It writes the blend file to a temporary location, configures
    Blender for GPU rendering, renders the frame, and returns
    the rendered image data.

    Args:
        frame_number: Frame number to render
        blend_file_data: Binary content of the .blend file
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
    import os
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

        # Create temporary directory for render operation
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Write blend file to temporary location
            blend_file_path = tmpdir_path / "scene.blend"
            with open(blend_file_path, "wb") as f:
                f.write(blend_file_data)

            print(f"Rendering frame {frame_number} with {render_config.get('engine', 'CYCLES')}")
            print(f"GPU: {result['gpu_info']}")

            # Build output path
            output_path = tmpdir_path / output_filename

            # Build Blender Python script for render configuration
            python_script_parts = [
                "import bpy",
                f"bpy.context.scene.frame_set({frame_number})",
                f"bpy.context.scene.render.filepath = '{output_path}'",
            ]

            # Apply render settings
            config = render_config

            if config.get('engine'):
                python_script_parts.append(
                    f"bpy.context.scene.render.engine = '{config['engine']}'"
                )

            if config.get('samples'):
                python_script_parts.append(
                    f"bpy.context.scene.cycles.samples = {config['samples']}"
                )

            if config.get('resolution_percentage'):
                python_script_parts.append(
                    f"bpy.context.scene.render.resolution_percentage = {config['resolution_percentage']}"
                )

            if config.get('denoising'):
                python_script_parts.append(
                    "bpy.context.scene.cycles.use_denoising = True"
                )

            if config.get('format'):
                python_script_parts.append(
                    f"bpy.context.scene.render.image_settings.file_format = '{config['format']}'"
                )

            # Configure GPU rendering
            if config.get('device') == 'GPU':
                python_script_parts.extend([
                    # Try to set CUDA as compute device
                    "import bpy",
                    "prefs = bpy.context.preferences.addons.get('cycles')",
                    "if prefs:",
                    "    prefs = prefs.preferences",
                    "    # Try CUDA first, fall back to OPTIX",
                    "    for compute_device_type in ['CUDA', 'OPTIX']:",
                    "        try:",
                    "            prefs.compute_device_type = compute_device_type",
                    "            prefs.get_devices()",
                    "            break",
                    "        except: pass",
                    "    # Enable all available GPU devices",
                    "    for device in prefs.devices:",
                    "        device.use = True",
                    "bpy.context.scene.cycles.device = 'GPU'",
                ])

            python_script = "; ".join(python_script_parts)

            # Build Blender command
            cmd = [
                "blender",
                "--background",
                str(blend_file_path),
                "--python-expr",
                python_script,
                "--render-frame",
                str(frame_number),
            ]

            # Execute Blender render
            print(f"Executing: {' '.join(cmd[:3])}...")
            render_process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3000,  # 50 minute timeout
            )

            if render_process.returncode != 0:
                result["error"] = f"Blender process failed with code {render_process.returncode}"
                result["error"] += f"\nSTDOUT: {render_process.stdout[-1000:]}"  # Last 1000 chars
                result["error"] += f"\nSTDERR: {render_process.stderr[-1000:]}"
                print(result["error"])
                return result

            # Check if output file was created
            # Blender may add frame number to filename
            possible_outputs = [
                output_path,
                output_path.with_suffix(f".{frame_number:04d}{output_path.suffix}"),
                tmpdir_path / f"{output_path.stem}{frame_number:04d}{output_path.suffix}",
            ]

            output_file = None
            for possible_output in possible_outputs:
                if possible_output.exists():
                    output_file = possible_output
                    break

            if not output_file or not output_file.exists():
                # List directory contents for debugging
                dir_contents = list(tmpdir_path.glob("*"))
                result["error"] = f"Output file not found. Expected: {output_path}. Directory contents: {dir_contents}"
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
    1. Uploads the .blend file (reads into memory as bytes)
    2. Distributes frames across parallel Modal containers
    3. Launches rendering jobs using the render_single_frame function
    4. Downloads rendered frames back to local output directory

    Args:
        blend_file: Path to the .blend file
        frames: List of frame numbers to render
        output_dir: Local directory to save rendered frames
        render_config: Render configuration dictionary
        gpu_type: GPU type to use (A10G, A100, etc.)

    Returns:
        Dictionary with render results and statistics including:
            - status: "success", "partial_failure", or "error"
            - frames_rendered: Number of successfully rendered frames
            - total_time: Total rendering time in seconds
            - output_dir: Path to output directory
            - failed_frames: List of frame numbers that failed (if any)
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

    # Step 1: Upload blend file (read into memory)
    print(f"\n[1/3] Loading .blend file...")
    try:
        with open(blend_path, "rb") as f:
            blend_file_data = f.read()
        print(f"✓ Loaded {len(blend_file_data)} bytes")
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to read blend file: {str(e)}",
            "frames_rendered": 0,
        }

    # Prepare default render config
    config = render_config or {}

    # Step 2: Distribute frames across parallel containers and launch render jobs
    print(f"\n[2/3] Distributing {len(frames)} frames across parallel containers...")
    print(f"Launching render jobs on Modal with {gpu_type} GPUs...")

    try:
        # Prepare render tasks for all frames
        render_tasks = [
            (
                frame_num,
                blend_file_data,
                f"frame_{frame_num:04d}.png",
                config,
            )
            for frame_num in frames
        ]

        # Execute rendering in parallel using Modal's starmap
        # This distributes the frames across available containers
        with app.run():
            # Configure GPU type for this run
            render_fn = render_single_frame
            if gpu_type != "A10G":
                # Create a new function with different GPU if needed
                render_fn = modal.Function.from_name(
                    app, "render_single_frame"
                ).with_options(gpu=gpu_type)

            results = list(render_fn.starmap(render_tasks))

        # Analyze results
        successful_frames = [r for r in results if r.get("success")]
        failed_frames = [r for r in results if not r.get("success")]

        print(f"✓ Rendering completed: {len(successful_frames)} successful, {len(failed_frames)} failed")

        if failed_frames:
            print("\nFailed frames:")
            for failed in failed_frames[:5]:  # Show first 5 failures
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
                # Write frame to output directory
                output_file = output_path / f"frame_{frame_num:04d}.png"
                with open(output_file, "wb") as f:
                    f.write(frame_data)
                downloaded_files.append(output_file)
        except Exception as e:
            print(f"Warning: Failed to save frame {result.get('frame_number')}: {e}")
            continue

    print(f"✓ Downloaded {len(downloaded_files)} frames")

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
