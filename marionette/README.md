# Marionette

Blender rendering framework with Modal cloud GPU support for distributed, high-performance rendering.

## Features

- 🖥️ **Local Rendering**: Traditional Blender command-line rendering
- ☁️ **Modal Cloud Rendering**: Distributed GPU rendering across multiple containers
- 🎨 **Rich CLI**: Beautiful terminal UI with progress tracking and status displays
- ⚙️ **Flexible Configuration**: Python API and CLI with preset support
- 🚀 **GPU Support**: A10G, A100, and T4 GPU options for cloud rendering
- 📊 **Progress Tracking**: Real-time container status and render progress

## Installation

```bash
cd marionette
pip install -e .
```

## Quick Start

### Local Rendering

```python
from marionette import Renderer, RenderConfig

config = RenderConfig(
    blend_file="scene.blend",
    output_dir="./output",
    frame_start=1,
    frame_end=30,
    use_modal=False,
    render_settings={
        "engine": "CYCLES",
        "samples": 128,
        "resolution_percentage": 100,
    }
)

renderer = Renderer()
renderer.render_sequence(config)
```

### Modal Cloud Rendering

```python
from marionette import Renderer, RenderConfig

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
    }
)

renderer = Renderer()
renderer.render_sequence(config)
```

## CLI Usage

### Local Rendering

```bash
marionette render --local \
  --blend-file scene.blend \
  --frames 1-30 \
  --output-dir ./output
```

### Modal Cloud Rendering

```bash
marionette render --modal \
  --blend-file scene.blend \
  --frames 1-100 \
  --gpu-type A10G \
  --parallel-containers 8 \
  --output-dir ./output
```

### With Render Preset

```bash
marionette render --modal \
  --blend-file scene.blend \
  --frames 1-100 \
  --preset high_quality \
  --gpu-type A100 \
  --output-dir ./output
```

## CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--modal/--local` | Use Modal cloud or local rendering | `--local` |
| `--blend-file` | Path to .blend file | Required |
| `--frames` | Frame range (e.g., "1-100") | Required |
| `--output-dir` | Output directory | `./output` |
| `--gpu-type` | GPU type (A10G, A100, T4) | `A10G` |
| `--parallel-containers` | Number of parallel containers | `4` |
| `--preset` | Render preset name | None |
| `--samples` | Number of render samples | From preset |
| `--resolution-percentage` | Resolution percentage | From preset |

## RenderConfig Parameters

### Required Parameters

- `blend_file` (str): Path to .blend file
- `output_dir` (str): Output directory for rendered frames
- `frame_start` (int): First frame to render
- `frame_end` (int): Last frame to render

### Optional Parameters

- `use_modal` (bool): Use Modal cloud rendering (default: False)
- `gpu_type` (str): GPU type for Modal ("A10G", "A100", "T4") - requires `use_modal=True`
- `parallel_containers` (int): Number of parallel containers (default: 4) - requires `use_modal=True`
- `render_settings` (dict): Render settings dictionary
- `blender_executable` (str): Path to Blender executable (default: "blender")

### Render Settings Dictionary

```python
render_settings = {
    "engine": "CYCLES",              # Render engine
    "samples": 256,                  # Number of samples
    "resolution_percentage": 100,    # Resolution percentage
    "denoising": True,              # Enable denoising
    "device": "GPU",                # Device type (local only)
    "format": "PNG",                # Output format
}
```

## GPU Types

| GPU Type | Use Case | Relative Cost | Performance |
|----------|----------|---------------|-------------|
| T4 | Budget-friendly, simple scenes | $ | Good |
| A10G | Balanced performance/cost | $$ | Better |
| A100 | High-performance, complex scenes | $$$ | Best |

## Validation

The `RenderConfig` class includes validation to ensure Modal-specific options are only used when appropriate:

```python
# ✓ Valid: Modal with GPU type
config = RenderConfig(
    blend_file="scene.blend",
    output_dir="./output",
    frame_start=1,
    frame_end=100,
    use_modal=True,
    gpu_type="A10G",
)

# ✗ Invalid: GPU type without Modal
config = RenderConfig(
    blend_file="scene.blend",
    output_dir="./output",
    frame_start=1,
    frame_end=100,
    use_modal=False,
    gpu_type="A10G",  # ValidationError!
)
```

## Output Structure

Rendered frames are saved with consistent naming for compatibility with VideoStitcher:

```
output_dir/
├── frame_0001.png
├── frame_0002.png
├── frame_0003.png
└── ...
```

## Examples

See the `examples/` directory for complete demo scripts:

- `demo_local_render.py`: Local rendering examples
- `demo_modal_render.py`: Modal cloud rendering examples with different GPU types

## Architecture

### Module Overview

- `render.py`: Core `Renderer` class and `RenderConfig` model
- `modal_render.py`: Modal cloud GPU rendering infrastructure
- `cli.py`: Click CLI with Rich terminal UI

### Renderer Flow

```
User Input
    ↓
RenderConfig (validation)
    ↓
Renderer.render_sequence()
    ↓
    ├─→ Local: Blender CLI
    └─→ Modal: modal_render.render_frames_remote()
         ↓
         Modal Containers (parallel)
         ↓
         Download frames
    ↓
Output Directory
```

## Backward Compatibility

The `Renderer` class maintains backward compatibility with legacy methods:

```python
renderer = Renderer()

# Legacy method (still works)
renderer.render_scene(
    blend_file="scene.blend",
    output_path="./output/frame_####.png",
    frame_start=1,
    frame_end=30,
    render_config={"samples": 128}
)

# New method (recommended)
config = RenderConfig(
    blend_file="scene.blend",
    output_dir="./output",
    frame_start=1,
    frame_end=30,
    render_settings={"samples": 128}
)
renderer.render_sequence(config)
```

## Development

### Running Tests

```bash
pytest tests/
```

### Installing in Development Mode

```bash
pip install -e ".[dev]"
```

## License

See the main project LICENSE file.

## Credits

🤖 Generated with [Claude Code](https://claude.com/claude-code)
