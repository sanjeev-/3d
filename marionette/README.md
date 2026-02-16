# Marionette

Cloud GPU rendering for Blender projects using [Modal](https://modal.com).

## Features

- **Cloud GPU Rendering**: Leverage Modal's cloud infrastructure with NVIDIA A10G/A100 GPUs
- **Parallel Rendering**: Distribute frames across multiple containers for faster rendering
- **Blender 3.6+ Support**: Uses latest Blender LTS with Cycles GPU rendering
- **Easy Integration**: Drop-in replacement for local rendering workflows
- **CLI Support**: Command-line interface for both local and cloud rendering

## Installation

```bash
cd marionette
pip install -e .
```

## Quick Start

### Prerequisites

1. Install Modal and authenticate:
   ```bash
   pip install modal
   modal token new
   ```

2. Ensure you have a Modal account with GPU access

### Python API

#### Unified Renderer API (Recommended)

```python
from marionette import Renderer, RenderConfig

# Local rendering
config = RenderConfig(
    blend_file="scene.blend",
    output_dir="./output",
    frame_start=1,
    frame_end=100,
    use_modal=False,
    render_settings={
        "engine": "CYCLES",
        "device": "GPU",
        "samples": 128,
        "denoising": True,
    }
)

renderer = Renderer()
renderer.render_sequence(config)

# Modal cloud rendering
config = RenderConfig(
    blend_file="scene.blend",
    output_dir="./output",
    frame_start=1,
    frame_end=100,
    use_modal=True,
    gpu_type="A10G",
    parallel_containers=8,
    render_settings={
        "engine": "CYCLES",
        "samples": 256,
        "denoising": True,
    }
)

renderer = Renderer()
renderer.render_sequence(config)
```

#### Direct Modal API

```python
from marionette import render_frames_remote

# Render frames 1-100 using cloud GPUs
results = render_frames_remote(
    blend_file="scene.blend",
    frames=list(range(1, 101)),
    output_dir="./renders",
    render_config={
        "engine": "CYCLES",
        "device": "GPU",
        "samples": 128,
        "denoising": True,
    },
    gpu_type="A10G"
)
```

### CLI

```bash
# Local rendering with preview preset
marionette render --local --blend-file scene.blend --frames 1-120 --preset preview

# Cloud rendering with high quality preset on A100 GPU
marionette render --modal --blend-file scene.blend --frames 1-120 --preset high_quality --gpu-type A100

# Render specific frames only
marionette render --local --blend-file scene.blend --frames "1,10,20,30"
```

## Commands

### `marionette render`

Render Blender scenes locally or on Modal cloud infrastructure.

**Options:**

- `--modal/--local` - Use Modal cloud rendering or local rendering (default: local)
- `--frames TEXT` - Frame range to render (e.g., "1-120" or "1,5,10") [default: 1-10]
- `--preset TEXT` - Render quality preset: preview, medium, high_quality, final [default: preview]
- `--gpu-type [A10G|A100]` - GPU type for Modal cloud rendering [default: A10G]
- `--blend-file PATH` - Path to the .blend file to render [required]
- `--output-dir PATH` - Output directory for rendered frames [default: ./output]

## Render Presets

Presets are loaded from `config/render_presets.yaml`:

- **preview** - Fast preview (32 samples, 50% resolution)
- **medium** - Balanced quality (128 samples)
- **high_quality** - High quality (512 samples)
- **final** - Maximum quality (1024 samples)

## Architecture

Marionette creates a Modal app with:

- **Container Image**: Debian-based image with Blender 3.6, CUDA drivers, and Python dependencies
- **GPU Functions**: Modal functions decorated with GPU specifications (A10G, A100, etc.)
- **Distributed Rendering**: Frames are distributed across parallel containers
- **File Transfer**: Automatic upload/download of .blend files and rendered frames

## Development Status

This is part of a multi-ticket implementation:

- ✅ Ticket #1-2: Modal rendering module (completed)
- ✅ Ticket #3: CLI foundation (completed)
- ✅ Ticket #4: Rich UI for progress tracking (completed)
- ✅ **Ticket #5: Integration with existing Renderer** (completed)

## Development

```bash
# Install in development mode with dev dependencies
pip install -e "marionette[dev]"

# Run tests
pytest

# Format code
black src/
```

## Requirements

- Python 3.9+
- modal >= 0.63.0
- pydantic >= 2.0.0
- pyyaml >= 6.0
- click >= 8.0.0
- rich >= 13.0.0

## License

MIT
