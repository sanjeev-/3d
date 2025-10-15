"""
Compositing and video export utilities.
"""

import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml


class Compositor:
    """
    Handles video compositing and export using FFmpeg.

    Combines rendered frames into final video output with proper
    encoding settings.
    """

    def __init__(self, ffmpeg_executable: str = "ffmpeg"):
        """
        Initialize the compositor.

        Args:
            ffmpeg_executable: Path to FFmpeg executable
        """
        self.ffmpeg_executable = ffmpeg_executable

    def frames_to_video(self, frames_pattern: str, output_path: str,
                       fps: int = 24, start_number: int = 1,
                       codec_config: Optional[Dict[str, Any]] = None,
                       audio_path: Optional[str] = None) -> int:
        """
        Combine rendered frames into a video file.

        Args:
            frames_pattern: Pattern for input frames (e.g., "frame_%04d.png")
            output_path: Output video file path
            fps: Frames per second
            start_number: Starting frame number
            codec_config: Codec configuration
            audio_path: Optional audio file to include

        Returns:
            Return code from FFmpeg process
        """
        config = codec_config or self._get_default_codec_config()

        # Build FFmpeg command
        cmd = [
            self.ffmpeg_executable,
            "-y",  # Overwrite output
            "-framerate", str(fps),
            "-start_number", str(start_number),
            "-i", frames_pattern,
        ]

        # Add audio if provided
        if audio_path:
            cmd.extend(["-i", audio_path])

        # Add codec settings
        if 'codec' in config:
            cmd.extend(["-c:v", config['codec']])

        if 'preset' in config:
            cmd.extend(["-preset", config['preset']])

        if 'crf' in config:
            cmd.extend(["-crf", str(config['crf'])])

        if 'pixel_format' in config:
            cmd.extend(["-pix_fmt", config['pixel_format']])

        # Audio settings
        if audio_path and 'audio_codec' in config:
            cmd.extend(["-c:a", config['audio_codec']])
            if 'audio_bitrate' in config:
                cmd.extend(["-b:a", config['audio_bitrate']])

        cmd.append(output_path)

        # Execute FFmpeg
        print(f"Encoding video to {output_path}...")
        result = subprocess.run(cmd, capture_output=False)

        return result.returncode

    def concatenate_videos(self, video_paths: List[str], output_path: str,
                          codec_config: Optional[Dict[str, Any]] = None) -> int:
        """
        Concatenate multiple video files.

        Args:
            video_paths: List of input video file paths
            output_path: Output video file path
            codec_config: Codec configuration

        Returns:
            Return code from FFmpeg process
        """
        # Create concat list file
        concat_file = Path(output_path).parent / "concat_list.txt"
        with open(concat_file, 'w') as f:
            for video_path in video_paths:
                f.write(f"file '{video_path}'\n")

        config = codec_config or self._get_default_codec_config()

        # Build FFmpeg command
        cmd = [
            self.ffmpeg_executable,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
        ]

        # Add codec settings
        if 'codec' in config:
            cmd.extend(["-c:v", config['codec']])

        cmd.append(output_path)

        # Execute FFmpeg
        print(f"Concatenating {len(video_paths)} videos...")
        result = subprocess.run(cmd, capture_output=False)

        # Clean up concat list
        concat_file.unlink()

        return result.returncode

    def add_audio(self, video_path: str, audio_path: str, output_path: str,
                 audio_offset: float = 0.0) -> int:
        """
        Add audio track to a video file.

        Args:
            video_path: Input video file
            audio_path: Input audio file
            output_path: Output video file
            audio_offset: Audio offset in seconds

        Returns:
            Return code from FFmpeg process
        """
        cmd = [
            self.ffmpeg_executable,
            "-y",
            "-i", video_path,
            "-itsoffset", str(audio_offset),
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            output_path
        ]

        print(f"Adding audio to {video_path}...")
        result = subprocess.run(cmd, capture_output=False)

        return result.returncode

    def _get_default_codec_config(self) -> Dict[str, Any]:
        """Get default H.264 codec configuration."""
        return {
            'codec': 'libx264',
            'preset': 'medium',
            'crf': 18,
            'pixel_format': 'yuv420p',
            'audio_codec': 'aac',
            'audio_bitrate': '320k'
        }

    def load_export_preset(self, preset_file: str, codec_name: str) -> Dict[str, Any]:
        """
        Load an export preset from a YAML file.

        Args:
            preset_file: Path to export settings YAML file
            codec_name: Name of the codec preset to load

        Returns:
            Codec configuration dict
        """
        with open(preset_file, 'r') as f:
            settings = yaml.safe_load(f)

        if codec_name not in settings.get('video_codecs', {}):
            raise ValueError(f"Codec '{codec_name}' not found in {preset_file}")

        config = settings['video_codecs'][codec_name].copy()

        # Add audio settings
        if 'audio' in settings:
            config['audio_codec'] = settings['audio'].get('codec', 'aac')
            config['audio_bitrate'] = settings['audio'].get('bitrate', '320k')

        return config
