# Blender Movies

A well-structured repository for creating animated movies in Blender with Python automation, good abstractions, and reproducible workflows.

## Features

- **Declarative movie definitions** using YAML
- **Modular architecture** with reusable components
- **Command-line tools** for rendering and exporting
- **Preset system** for render and export settings
- **Multi-scene support** with automatic compositing
- **Git-friendly** with LFS support for large files

## Directory Structure

```
blender-movies/
├── config/                    # Global configuration
│   ├── render_presets.yaml   # Render quality presets
│   └── export_settings.yaml  # Video codec settings
├── movies/                    # Individual movie projects
│   └── movie_001_demo/       # Example movie
│       ├── definition.yaml   # Movie configuration
│       ├── blender/          # Blender files
│       ├── renders/          # Rendered output
│       └── scripts/          # Custom scripts
├── shared/                    # Shared resources
│   ├── assets/               # Reusable assets
│   ├── scripts/              # Core library
│   │   ├── core/            # Main abstractions
│   │   └── utils/           # Utilities
│   └── presets/             # Template blend files
├── scripts/                   # Command-line tools
│   ├── build_movie.py        # Render movies
│   ├── batch_render.py       # Batch processing
│   └── export_final.py       # Video export
└── tests/                     # Test suite
```

## Quick Start

### Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd blender-movies
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Set up Git LFS for large files:
```bash
git lfs install
git lfs track "*.blend"
git lfs track "*.mp4"
```

### Create Your First Movie

1. Create a new movie directory:
```bash
mkdir -p movies/my_movie/{blender/scenes,renders/frames,renders/final,scripts}
```

2. Create a `definition.yaml` (see example in `movies/movie_001_demo/`)

3. Create your Blender scene file(s)

4. Render the movie:
```bash
python scripts/build_movie.py movies/my_movie/definition.yaml
```

5. Export to video:
```bash
python scripts/export_final.py movies/my_movie/definition.yaml
```

## Usage

### Building a Movie

Render all scenes:
```bash
python scripts/build_movie.py movies/my_movie/definition.yaml
```

Render specific scene:
```bash
python scripts/build_movie.py movies/my_movie/definition.yaml --scene intro
```

Use render preset:
```bash
python scripts/build_movie.py movies/my_movie/definition.yaml --preset preview
```

Validate without rendering:
```bash
python scripts/build_movie.py movies/my_movie/definition.yaml --dry-run
```

### Batch Rendering

Render multiple movies:
```bash
python scripts/batch_render.py movies/movie_001_demo movies/movie_002_short
```

Continue on errors:
```bash
python scripts/batch_render.py movies/* --continue-on-error
```

### Exporting Video

Export with default settings:
```bash
python scripts/export_final.py movies/my_movie/definition.yaml
```

Choose codec:
```bash
python scripts/export_final.py movies/my_movie/definition.yaml --codec h265
```

Add audio:
```bash
python scripts/export_final.py movies/my_movie/definition.yaml --audio soundtrack.wav
```

Custom output path:
```bash
python scripts/export_final.py movies/my_movie/definition.yaml --output final.mp4
```

## Movie Definition Format

Example `definition.yaml`:

```yaml
movie:
  title: "My Movie"
  version: "1.0"
  resolution: [1920, 1080]
  fps: 24
  duration_frames: 240

scenes:
  - name: "intro"
    blend_file: "blender/scenes/intro.blend"
    frame_range: [1, 60]

  - name: "main"
    blend_file: "blender/main.blend"
    frame_range: [61, 240]

assets:
  shared:
    - "../../shared/assets/hdris/studio.hdr"
  local:
    - "blender/assets/props.blend"

render:
  engine: "CYCLES"
  device: "GPU"
  samples: 128
  preset: "high_quality"
  denoising: true

output:
  format: "PNG"
  final_video: "renders/final/my_movie.mp4"
  codec: "h264"
```

## Render Presets

Available in `config/render_presets.yaml`:

- **preview** - Fast preview (32 samples, 50% resolution)
- **medium** - Balanced quality (128 samples)
- **high_quality** - High quality (512 samples)
- **final** - Maximum quality (1024 samples)

## Video Codecs

Available in `config/export_settings.yaml`:

- **h264** - H.264/AVC (widely compatible)
- **h265** - H.265/HEVC (better compression)
- **prores** - ProRes 422 HQ (professional)

## Core API

The `shared/scripts/core` module provides Python abstractions:

### MovieProject

```python
from core import MovieProject

project = MovieProject("movies/my_movie/definition.yaml")
project.setup_output_directories()
project.validate()

for scene in project.scenes:
    print(scene.name, scene.frame_start, scene.frame_end)
```

### Renderer

```python
from core import Renderer

renderer = Renderer(blender_executable="blender")
renderer.render_scene(
    blend_file="scene.blend",
    output_path="output/frame_####.png",
    frame_start=1,
    frame_end=120,
    render_config={"engine": "CYCLES", "samples": 128}
)
```

### Compositor

```python
from core import Compositor

compositor = Compositor()
compositor.frames_to_video(
    frames_pattern="frames/frame_%04d.png",
    output_path="output.mp4",
    fps=24,
    codec_config={"codec": "libx264", "crf": 18}
)
```

## Custom Scripts

You can write custom Python scripts that run inside Blender to set up scenes, create procedural content, or automate tasks. See `movies/movie_001_demo/scripts/custom_animation.py` for an example.

Run a custom script:
```bash
blender --background scene.blend --python my_script.py
```

## Git LFS Setup

For large files (.blend, .mp4, .hdr, etc.), use Git LFS:

```bash
git lfs install
git lfs track "*.blend"
git lfs track "*.mp4"
git lfs track "*.hdr"
git add .gitattributes
git commit -m "Add Git LFS tracking"
```

## Best Practices

1. **Version control movie definitions** - YAML files are easy to diff and merge
2. **Use render presets** - Consistent quality across projects
3. **Keep renders out of git** - They're regenerable and large
4. **Share assets** - Put reusable content in `shared/assets/`
5. **Document custom scripts** - Future you will thank you
6. **Test with preview preset** - Save time during development

## Troubleshooting

### Blender not found
```bash
python scripts/build_movie.py definition.yaml --blender /path/to/blender
```

### FFmpeg not found
```bash
python scripts/export_final.py definition.yaml --ffmpeg /path/to/ffmpeg
```

### Out of memory during render
Use the preview preset or reduce samples:
```bash
python scripts/build_movie.py definition.yaml --preset preview
```

### Blend file not found
Check paths in `definition.yaml` are relative to the definition file location.

## Contributing

1. Create a new branch for your movie
2. Keep movie projects in `movies/` directory
3. Share reusable assets in `shared/assets/`
4. Update documentation for new features

## License

[Your license here]

## Resources

- [Blender Manual](https://docs.blender.org/)
- [Blender Python API](https://docs.blender.org/api/current/)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
