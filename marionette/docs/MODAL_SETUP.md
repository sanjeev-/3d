# Modal Cloud GPU Rendering Setup

This document explains the Modal cloud infrastructure setup for Marionette's GPU rendering capabilities.

## Overview

Marionette uses [Modal](https://modal.com) to provide scalable cloud GPU rendering for Blender projects. The setup includes:

1. **Container Image**: Custom Debian-based image with Blender 3.6+ and CUDA support
2. **GPU Functions**: Modal functions that execute on cloud GPUs (A10G, A100)
3. **Distributed Rendering**: Parallel execution across multiple containers

## Container Image

The `blender_image` is built using Modal's image builder:

```python
blender_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "wget", "xz-utils", "libgl1", "libglu1-mesa",
        "libsm6", "libxi6", "libxrender1", "libxkbcommon0", "libgomp1"
    )
    .run_commands(
        # Download Blender 3.6.9 LTS
        "wget -q https://download.blender.org/release/Blender3.6/blender-3.6.9-linux-x64.tar.xz",
        # Extract and install
        "tar -xf /tmp/blender.tar.xz -C /opt/",
        # Symlink to PATH
        "ln -s /opt/blender/blender /usr/local/bin/blender"
    )
    .pip_install("pydantic>=2.0.0", "pyyaml>=6.0")
)
```

### Image Components

- **Base**: Debian Slim with Python 3.11
- **Blender**: Version 3.6.9 LTS (latest stable)
- **CUDA**: Automatically provided by Modal's GPU infrastructure
- **Python Packages**: Pydantic for data validation, PyYAML for config

## GPU Rendering Function

The `render_single_frame` function is decorated with Modal's function decorator:

```python
@app.function(
    image=blender_image,
    gpu="A10G",           # GPU type
    timeout=3600,         # 1 hour timeout
    retries=2,            # Retry on failure
)
def render_single_frame(...):
    # GPU rendering logic
    pass
```

### GPU Configuration

The function automatically:

1. Detects available GPU using `nvidia-smi`
2. Configures Blender to use CUDA/OPTIX
3. Enables all available GPU devices
4. Sets Cycles to GPU rendering mode

### Error Handling

The function includes comprehensive error handling:

- **GPU Detection**: Falls back gracefully if GPU info unavailable
- **Render Failures**: Captures stdout/stderr for debugging
- **Timeout Protection**: 50-minute subprocess timeout (within 1-hour function timeout)
- **File Validation**: Checks for output files with multiple naming patterns

## Render Configuration

The `RenderConfig` Pydantic model validates render settings:

```python
class RenderConfig(BaseModel):
    engine: str = "CYCLES"                    # CYCLES or EEVEE
    device: str = "GPU"                       # GPU or CPU
    samples: int = 128                        # Render samples
    resolution_percentage: int = 100          # Resolution scale
    denoising: bool = True                    # Enable denoising
    format: str = "PNG"                       # Output format
```

## GPU Types

Modal supports multiple GPU types:

- **A10G**: 24GB VRAM, good for most renders (~$1.10/hour)
- **A100**: 40GB/80GB VRAM, for heavy scenes (~$4.00/hour)
- **T4**: 16GB VRAM, economical option (~$0.60/hour)

Select based on your scene complexity and budget.

## Usage Example

```python
# This will be available after task #2
from marionette import render_frames_remote

results = render_frames_remote(
    blend_file="animation.blend",
    frames=[1, 2, 3, 4, 5],
    output_dir="./renders",
    render_config={
        "engine": "CYCLES",
        "device": "GPU",
        "samples": 256,
        "denoising": True,
    },
    gpu_type="A10G"
)
```

## Authentication

Before using Modal, you need to authenticate:

```bash
# Install Modal CLI
pip install modal

# Authenticate (opens browser)
modal token new

# Verify setup
modal app list
```

## Deployment

The Modal app is automatically deployed when you call functions:

```python
# Runs locally, deploys to Modal when called
with app.run():
    result = render_single_frame.remote(...)
```

For production, you can deploy the app:

```bash
modal deploy marionette/src/marionette/modal_render.py
```

## Cost Estimation

Approximate costs per frame (varies by scene complexity):

- **A10G**: $0.02 - $0.10 per frame (simple to medium scenes)
- **A100**: $0.05 - $0.30 per frame (complex scenes)

For a 30-second animation (720 frames at 24fps):
- A10G: ~$15-70
- A100: ~$36-216

Still much cheaper than buying your own GPU workstation!

## Monitoring

Monitor your renders through:

1. **Modal Dashboard**: https://modal.com/apps
2. **Function Logs**: Real-time stdout/stderr in dashboard
3. **GPU Utilization**: Visible in Modal UI
4. **Cost Tracking**: Automatic billing dashboard

## Troubleshooting

### GPU Not Found
- Check Modal dashboard for GPU availability
- Try different GPU type (A10G vs A100)
- Verify Modal account has GPU access

### Render Timeout
- Increase timeout parameter for complex scenes
- Reduce samples or resolution
- Split into smaller frame batches

### Out of Memory
- Reduce render resolution
- Simplify scene geometry
- Use GPU with more VRAM (A100 80GB)

### Blender Errors
- Check logs in Modal dashboard
- Verify .blend file compatibility with Blender 3.6
- Ensure all assets are embedded or available

## Next Steps

After task #1 (current), the following will be added:

- **Task #2**: File upload/download and frame distribution
- **Task #3**: CLI interface with Click
- **Task #4**: Rich UI for progress tracking
- **Task #5**: Integration with existing Renderer class

## Resources

- [Modal Documentation](https://modal.com/docs)
- [Blender Python API](https://docs.blender.org/api/current/)
- [Cycles GPU Rendering](https://docs.blender.org/manual/en/latest/render/cycles/gpu_rendering.html)
