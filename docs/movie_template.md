# Movie Project Template

Use this template to create new movie projects.

## Directory Setup

```bash
# Create movie directory structure
mkdir -p movies/YOUR_MOVIE_NAME/{blender/scenes,blender/assets,renders/frames,renders/final,scripts}

# Create placeholder files
touch movies/YOUR_MOVIE_NAME/definition.yaml
touch movies/YOUR_MOVIE_NAME/blender/main.blend
touch movies/YOUR_MOVIE_NAME/renders/frames/.gitkeep
touch movies/YOUR_MOVIE_NAME/renders/final/.gitkeep
```

## Minimal definition.yaml

```yaml
movie:
  title: "Your Movie Title"
  version: "1.0"
  resolution: [1920, 1080]
  fps: 24
  duration_frames: 240

scenes:
  - name: "main"
    blend_file: "blender/main.blend"
    frame_range: [1, 240]

render:
  engine: "CYCLES"
  device: "GPU"
  samples: 128
  preset: "medium"

output:
  final_video: "renders/final/output.mp4"
```

## Multi-Scene definition.yaml

```yaml
movie:
  title: "Your Movie Title"
  version: "1.0"
  resolution: [1920, 1080]
  fps: 24
  duration_frames: 480

scenes:
  - name: "intro"
    blend_file: "blender/scenes/intro.blend"
    frame_range: [1, 120]
    config:
      camera: "Camera.intro"

  - name: "main"
    blend_file: "blender/main.blend"
    frame_range: [121, 360]
    config:
      camera: "Camera.main"

  - name: "outro"
    blend_file: "blender/scenes/outro.blend"
    frame_range: [361, 480]
    config:
      camera: "Camera.outro"

assets:
  shared:
    - "../../shared/assets/hdris/studio.hdr"
    - "../../shared/assets/materials/common.blend"
  local:
    - "blender/assets/characters.blend"
    - "blender/assets/props.blend"

render:
  engine: "CYCLES"
  device: "GPU"
  samples: 256
  preset: "high_quality"
  denoising: true
  motion_blur: true

output:
  format: "PNG"
  final_video: "renders/final/movie.mp4"
  codec: "h264"

scene_overrides:
  intro:
    samples: 512  # Higher quality for intro
  outro:
    samples: 512
```

## Workflow

1. **Create your movie directory** using the structure above

2. **Edit definition.yaml** with your settings

3. **Create Blender files** in the appropriate locations

4. **Test render** with preview preset:
   ```bash
   python scripts/build_movie.py movies/YOUR_MOVIE_NAME/definition.yaml --preset preview
   ```

5. **Review frames** in `renders/frames/`

6. **Full render** when ready:
   ```bash
   python scripts/build_movie.py movies/YOUR_MOVIE_NAME/definition.yaml
   ```

7. **Export video**:
   ```bash
   python scripts/export_final.py movies/YOUR_MOVIE_NAME/definition.yaml
   ```

## Tips

- Start with a single scene to test your workflow
- Use preview preset during development to save time
- Keep blend files lightweight by linking assets instead of appending
- Add custom scripts in `scripts/` directory for procedural content
- Document your setup in a movie-specific README.md
