#!/usr/bin/env python3
"""
Export rendered frames to final video.

Usage:
    python export_final.py <definition_path> [--codec CODEC]
"""

import sys
import argparse
from pathlib import Path

# Add shared scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared" / "scripts"))

from core import MovieProject, Compositor
from utils import setup_logger, FileManager


def main():
    parser = argparse.ArgumentParser(description="Export rendered frames to final video")
    parser.add_argument("definition", help="Path to movie definition YAML file")
    parser.add_argument("--codec", "-c", default="h264", help="Video codec preset (h264, h265, prores)")
    parser.add_argument("--audio", "-a", help="Audio file to include")
    parser.add_argument("--output", "-o", help="Override output path")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="Path to FFmpeg executable")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Setup logging
    logger = setup_logger(level="DEBUG" if args.verbose else "INFO")

    try:
        # Load project
        logger.info(f"Loading project: {args.definition}")
        project = MovieProject(args.definition)
        logger.info(f"Loaded {project}")

        # Get movie configuration
        movie_config = project.movie_config
        fps = movie_config.get('fps', 24)

        # Load codec preset
        export_settings_file = Path(__file__).parent.parent / "config" / "export_settings.yaml"
        compositor = Compositor(args.ffmpeg)
        codec_config = compositor.load_export_preset(str(export_settings_file), args.codec)
        logger.info(f"Using codec: {args.codec}")

        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = project.get_output_path()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Process based on number of scenes
        if len(project.scenes) == 1:
            # Single scene - direct export
            scene = project.scenes[0]
            logger.info(f"Exporting single scene: {scene.name}")

            frames_dir = project.get_frames_dir(scene.name)
            frames_pattern = str(frames_dir / f"{scene.name}_%04d.png")

            result = compositor.frames_to_video(
                frames_pattern=frames_pattern,
                output_path=str(output_path),
                fps=fps,
                start_number=scene.frame_start,
                codec_config=codec_config,
                audio_path=args.audio
            )

            if result != 0:
                logger.error("Export failed")
                return result

        else:
            # Multiple scenes - render each then concatenate
            logger.info(f"Exporting {len(project.scenes)} scenes")
            temp_videos = []

            for scene in project.scenes:
                logger.info(f"Exporting scene: {scene.name}")

                frames_dir = project.get_frames_dir(scene.name)
                frames_pattern = str(frames_dir / f"{scene.name}_%04d.png")
                temp_output = frames_dir.parent / f"{scene.name}_temp.mp4"

                result = compositor.frames_to_video(
                    frames_pattern=frames_pattern,
                    output_path=str(temp_output),
                    fps=fps,
                    start_number=scene.frame_start,
                    codec_config=codec_config
                )

                if result != 0:
                    logger.error(f"Export failed for scene: {scene.name}")
                    return result

                temp_videos.append(str(temp_output))

            # Concatenate scenes
            logger.info("Concatenating scenes...")
            temp_concatenated = output_path.parent / "temp_concatenated.mp4"

            result = compositor.concatenate_videos(
                video_paths=temp_videos,
                output_path=str(temp_concatenated),
                codec_config=codec_config
            )

            if result != 0:
                logger.error("Concatenation failed")
                return result

            # Add audio if specified
            if args.audio:
                logger.info("Adding audio...")
                result = compositor.add_audio(
                    video_path=str(temp_concatenated),
                    audio_path=args.audio,
                    output_path=str(output_path)
                )

                if result != 0:
                    logger.error("Audio addition failed")
                    return result

                # Clean up temp concatenated file
                temp_concatenated.unlink()
            else:
                # Just rename temp file to final output
                temp_concatenated.rename(output_path)

            # Clean up temp scene videos
            for temp_video in temp_videos:
                Path(temp_video).unlink()

        # Show file size
        file_size = FileManager.get_file_size(str(output_path), human_readable=True)
        logger.info(f"\nExport complete!")
        logger.info(f"Output: {output_path}")
        logger.info(f"Size: {file_size}")

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
