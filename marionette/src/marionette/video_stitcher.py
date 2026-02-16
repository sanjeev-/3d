import os
import re
import subprocess
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VideoStitcher")

class VideoStitcher:
    """
    Utility to convert image sequences into video files using FFmpeg.
    Adheres to RenderConfig patterns to ensure sync between render and export.
    """

    @staticmethod
    def _convert_pattern_to_ffmpeg(pattern: str) -> str:
        """
        Converts a Python format string like 'render_{frame:04d}' 
        into an FFmpeg compatible pattern like 'render_%04d'.
        """
        # Regex looks for the {frame:NNd} pattern and extracts the digit NN
        ffmpeg_style = re.sub(r"\{frame:(\d+)d\}", r"%\1d", pattern)
        
        # Safety check: if no frame placeholder was found, FFmpeg won't know how to loop
        if "%" not in ffmpeg_style:
            logger.warning(f"Pattern '{pattern}' does not contain a valid frame placeholder (e.g., {{frame:04d}})")
        
        return ffmpeg_style

    @classmethod
    def create_video(
        cls, 
        config, # Passing the RenderConfig instance
        output_name: str = "output_video", 
        fps: int = 24,
        overwrite: bool = True
    ) -> Optional[str]:
        """
        Stitches images from the config's output_dir into an MP4.
        
        Returns:
            The path to the generated video file if successful, else None.
        """
        # 1. Prepare Paths
        input_dir = config.output_dir
        if not os.path.exists(input_dir):
            logger.error(f"Input directory does not exist: {input_dir}")
            return None

        # 2. Translate Naming Logic
        ffmpeg_pattern = cls._convert_pattern_to_ffmpeg(config.filename_pattern)
        ext = "png" if config.file_format.value == "PNG" else "jpg" # Maps Enum to extension
        
        input_path = os.path.join(input_dir, f"{ffmpeg_pattern}.{ext}")
        output_path = os.path.join(input_dir, f"{output_name}.mp4")

        # 3. Build FFmpeg Command
        # -y: overwrite
        # -framerate: set input fps
        # -i: input pattern
        # -c:v libx264: H.264 video codec
        # -pix_fmt yuv420p: Ensure compatibility with QuickTime/Phones
        # -crf 18: High quality (lower is better, 18-23 is standard)
        cmd = [
            'ffmpeg',
            '-y' if overwrite else '-n',
            '-framerate', str(fps),
            '-i', input_path,
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-crf', '18',
            output_path
        ]

        # 4. Execute
        logger.info(f"🎬 Stitching video: {output_path}")
        try:
            # check=True raises an error if FFmpeg fails
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("✅ Video encoding complete.")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ FFmpeg failed: {e.stderr}")
            return None
        except FileNotFoundError:
            logger.error("❌ FFmpeg not found. Please install it (brew install ffmpeg).")
            return None