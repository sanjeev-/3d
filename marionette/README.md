# Marionette

Cloud GPU rendering for Blender using Modal's serverless infrastructure.

## Features

- **Distributed Rendering**: Split frame ranges across multiple GPU containers
- **Cloud GPUs**: Leverage Modal's A10G, A100, and other GPU instances
- **Automatic File Transfer**: Seamless upload/download of blend files and rendered frames
- **Parallel Execution**: Render multiple frame ranges simultaneously
- **Simple CLI**: Easy-to-use command-line interface (coming soon)

## Installation

```bash
cd marionette
pip install -e .
```

## Setup

1. Install Modal CLI and authenticate:
```bash
pip install modal
modal token new
```

2. The first time you run a render, Modal will build the container image with Blender and CUDA support.

## Usage

### Python API

```python
from marionette.modal_render import render_frames_remote

result = render_frames_remote(
    blend_file="path/to/scene.blend",
    output_dir="output/frames",
    frame_start=1,
    frame_end=100,
    num_containers=4,
    gpu_type="A10G",
    render_config={
        "samples": 128,
        "resolution_percentage": 100,
        "denoising": True,
    }
)

print(f"Rendered {result['frames_rendered']} frames in {result['total_time']:.2f}s")
```

### CLI (Coming Soon)

```bash
marionette render scene.blend --modal --frames 1-100 --gpu-type A10G
```

## Configuration

Render configuration options:
- `engine`: Render engine (default: "CYCLES")
- `samples`: Number of samples for Cycles (default: 128)
- `resolution_percentage`: Render resolution as percentage (default: 100)
- `denoising`: Enable denoising (default: True)
- `format`: Output format (default: "PNG")

## Architecture

1. **File Upload**: Blend files are uploaded to Modal's persistent Volume
2. **Frame Distribution**: Frame range is split evenly across N containers
3. **Parallel Rendering**: Each container renders its assigned frames using GPU
4. **File Download**: Rendered frames are downloaded back to local directory

## License

MIT
