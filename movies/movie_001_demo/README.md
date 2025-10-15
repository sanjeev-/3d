# Demo Movie Project

A simple demonstration movie showing basic animation and rendering workflow.

## Project Structure

- `definition.yaml` - Movie configuration and scene definitions
- `blender/` - Blender files and assets
  - `main.blend` - Main scene file
  - `scenes/intro.blend` - Intro scene
  - `assets/` - Local assets for this movie
- `scripts/` - Custom Python scripts
  - `custom_animation.py` - Animation setup script
- `renders/` - Output directory for rendered frames and final video

## Getting Started

### 1. Create Blender Files

First, create the Blender scene files. You can use the custom animation script to set up a basic scene:

```bash
blender --background --python scripts/custom_animation.py --python-exit-code 1
```

Or open Blender and run the script from the scripting workspace.

### 2. Render the Movie

Render all scenes:

```bash
python ../../scripts/build_movie.py definition.yaml
```

Render specific scene:

```bash
python ../../scripts/build_movie.py definition.yaml --scene intro
```

Use a different render preset:

```bash
python ../../scripts/build_movie.py definition.yaml --preset preview
```

### 3. Export Final Video

Export rendered frames to video:

```bash
python ../../scripts/export_final.py definition.yaml
```

With H.265 codec:

```bash
python ../../scripts/export_final.py definition.yaml --codec h265
```

Add audio:

```bash
python ../../scripts/export_final.py definition.yaml --audio path/to/audio.wav
```

## Customization

Edit `definition.yaml` to:
- Change resolution or frame rate
- Adjust render settings
- Add more scenes
- Link shared assets

Edit `scripts/custom_animation.py` to:
- Create procedural animations
- Set up complex rigs
- Generate custom geometry
