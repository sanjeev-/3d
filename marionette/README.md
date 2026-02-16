# Marionette

Cloud GPU rendering for Blender projects using [Modal](https://modal.com).

## Features

- **Cloud GPU Rendering**: Leverage Modal's cloud infrastructure with NVIDIA A10G/A100 GPUs
- **Parallel Rendering**: Distribute frames across multiple containers for faster rendering
- **Blender 3.6+ Support**: Uses latest Blender LTS with Cycles GPU rendering
- **Easy Integration**: Drop-in replacement for local rendering workflows

## Installation

```bash
pip install -e marionette
```

For CLI support:
```bash
pip install -e "marionette[cli]"
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

### CLI (Coming Soon)

```bash
# Render using Modal cloud GPUs
marionette render scene.blend --modal --frames 1-100 --gpu-type A10G

# Render locally (default)
marionette render scene.blend --frames 1-100
```

## Architecture

Marionette creates a Modal app with:

- **Container Image**: Debian-based image with Blender 3.6, CUDA drivers, and Python dependencies
- **GPU Functions**: Modal functions decorated with GPU specifications (A10G, A100, etc.)
- **Distributed Rendering**: Frames are distributed across parallel containers
- **File Transfer**: Automatic upload/download of .blend files and rendered frames

## Development

```bash
# Install in development mode with dev dependencies
pip install -e "marionette[dev,cli]"

# Run tests
pytest

# Format code
black src/
```

## License

MIT
