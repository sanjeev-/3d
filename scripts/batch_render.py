#!/usr/bin/env python3
"""
Batch render multiple movie projects.

Usage:
    python batch_render.py <movie_dir1> <movie_dir2> ... [--preset PRESET]
"""

import sys
import argparse
from pathlib import Path
from typing import List

# Add shared scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared" / "scripts"))

from core import MovieProject, Renderer
from utils import setup_logger


def find_movie_definitions(directories: List[str]) -> List[Path]:
    """Find all definition.yaml files in given directories."""
    definitions = []

    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue

        # Check if directory itself contains definition.yaml
        def_file = dir_path / "definition.yaml"
        if def_file.exists():
            definitions.append(def_file)
        else:
            # Search for definition.yaml in subdirectories
            definitions.extend(dir_path.glob("*/definition.yaml"))

    return definitions


def main():
    parser = argparse.ArgumentParser(description="Batch render multiple Blender movie projects")
    parser.add_argument("directories", nargs="+", help="Movie project directories")
    parser.add_argument("--preset", "-p", help="Render preset to use")
    parser.add_argument("--blender", default="blender", help="Path to Blender executable")
    parser.add_argument("--continue-on-error", action="store_true",
                       help="Continue rendering other movies if one fails")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Setup logging
    logger = setup_logger(level="DEBUG" if args.verbose else "INFO")

    # Find all movie definitions
    logger.info("Searching for movie definitions...")
    definitions = find_movie_definitions(args.directories)

    if not definitions:
        logger.error("No movie definitions found")
        return 1

    logger.info(f"Found {len(definitions)} movie(s) to render")

    # Load render preset if specified
    render_config_override = None
    if args.preset:
        preset_file = Path(__file__).parent.parent / "config" / "render_presets.yaml"
        renderer = Renderer(args.blender)
        render_config_override = renderer.load_render_preset(str(preset_file), args.preset)
        logger.info(f"Using render preset: {args.preset}")

    # Initialize renderer
    renderer = Renderer(args.blender)

    # Render each movie
    failed_projects = []
    successful_projects = []

    for i, definition_path in enumerate(definitions, 1):
        logger.info(f"\n[{i}/{len(definitions)}] Processing: {definition_path.parent.name}")

        try:
            # Load project
            project = MovieProject(str(definition_path))

            # Validate
            errors = project.validate()
            if errors:
                logger.error("Validation failed:")
                for error in errors:
                    logger.error(f"  - {error}")
                failed_projects.append((definition_path, "Validation failed"))
                if not args.continue_on_error:
                    return 1
                continue

            # Setup output directories
            project.setup_output_directories()

            # Prepare render config
            render_config = project.render_config.copy()
            if render_config_override:
                render_config.update(render_config_override)

            # Render all scenes
            for scene in project.scenes:
                logger.info(f"Rendering scene: {scene.name}")

                frames_dir = project.get_frames_dir(scene.name)
                output_pattern = str(frames_dir / f"{scene.name}_####")

                result = renderer.render_scene(
                    blend_file=scene.blend_file,
                    output_path=output_pattern,
                    frame_start=scene.frame_start,
                    frame_end=scene.frame_end,
                    render_config=render_config
                )

                if result != 0:
                    raise RuntimeError(f"Render failed for scene: {scene.name}")

            successful_projects.append(definition_path)
            logger.info(f"Successfully rendered: {project.movie_config.get('title', 'Untitled')}")

        except Exception as e:
            logger.error(f"Error rendering {definition_path.parent.name}: {e}")
            failed_projects.append((definition_path, str(e)))

            if not args.continue_on_error:
                return 1

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Batch Render Summary")
    logger.info(f"{'='*60}")
    logger.info(f"Total projects: {len(definitions)}")
    logger.info(f"Successful: {len(successful_projects)}")
    logger.info(f"Failed: {len(failed_projects)}")

    if failed_projects:
        logger.warning("\nFailed projects:")
        for def_path, error in failed_projects:
            logger.warning(f"  - {def_path.parent.name}: {error}")

    return 0 if not failed_projects else 1


if __name__ == "__main__":
    sys.exit(main())
