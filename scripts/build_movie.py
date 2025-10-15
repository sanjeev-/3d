#!/usr/bin/env python3
"""
Build and render a movie project.

Usage:
    python build_movie.py <definition_path> [--scene SCENE] [--preset PRESET]
"""

import sys
import argparse
from pathlib import Path

# Add shared scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared" / "scripts"))

from core import MovieProject, Renderer
from utils import setup_logger


def main():
    parser = argparse.ArgumentParser(description="Build a Blender movie project")
    parser.add_argument("definition", help="Path to movie definition YAML file")
    parser.add_argument("--scene", "-s", help="Render specific scene only")
    parser.add_argument("--preset", "-p", help="Render preset to use (overrides definition)")
    parser.add_argument("--blender", default="blender", help="Path to Blender executable")
    parser.add_argument("--dry-run", action="store_true", help="Validate without rendering")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Setup logging
    logger = setup_logger(level="DEBUG" if args.verbose else "INFO")

    try:
        # Load project
        logger.info(f"Loading project: {args.definition}")
        project = MovieProject(args.definition)
        logger.info(f"Loaded {project}")

        # Validate
        errors = project.validate()
        if errors:
            logger.error("Project validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return 1

        logger.info("Project validation passed")

        # Setup output directories
        project.setup_output_directories()
        logger.info("Output directories created")

        if args.dry_run:
            logger.info("Dry run - skipping render")
            return 0

        # Load render preset if specified
        render_config = project.render_config.copy()
        if args.preset:
            preset_file = Path(__file__).parent.parent / "config" / "render_presets.yaml"
            renderer = Renderer(args.blender)
            preset_config = renderer.load_render_preset(str(preset_file), args.preset)
            render_config.update(preset_config)
            logger.info(f"Using render preset: {args.preset}")

        # Initialize renderer
        renderer = Renderer(args.blender)

        # Render scenes
        scenes_to_render = [project.get_scene(args.scene)] if args.scene else project.scenes

        if not scenes_to_render or (args.scene and not scenes_to_render[0]):
            logger.error(f"Scene not found: {args.scene}")
            return 1

        for scene in scenes_to_render:
            logger.info(f"Rendering scene: {scene.name}")

            # Determine output path
            frames_dir = project.get_frames_dir(scene.name)
            output_pattern = str(frames_dir / f"{scene.name}_####")

            # Render
            result = renderer.render_scene(
                blend_file=scene.blend_file,
                output_path=output_pattern,
                frame_start=scene.frame_start,
                frame_end=scene.frame_end,
                render_config=render_config
            )

            if result != 0:
                logger.error(f"Render failed for scene: {scene.name}")
                return result

            logger.info(f"Scene rendered successfully: {scene.name}")

        logger.info("All scenes rendered successfully!")
        logger.info(f"Frames saved to: {project.get_frames_dir()}")

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
