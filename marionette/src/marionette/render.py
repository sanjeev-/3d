import bpy
import os
import sys
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, Field
from tqdm import tqdm

class RenderEngine(str, Enum):
    CYCLES = "CYCLES"
    BLENDER_EEVEE = "BLENDER_EEVEE"
    BLENDER_EEVEE_NEXT = "BLENDER_EEVEE_NEXT"

class FileFormat(str, Enum):
    PNG = "PNG"
    JPEG = "JPEG"
    OPEN_EXR = "OPEN_EXR"
    FFMPEG = "FFMPEG"

class VideoCodec(str, Enum):
    H264 = "H264"
    DNXHD = "DNXHD"
    WEBM = "WEBM"

class RenderConfig(BaseModel):
    """Blueprint for render settings"""
    output_dir: str = "renders/output"
    engine: RenderEngine = RenderEngine.CYCLES
    samples: int = Field(default=128, ge=1)
    resolution: Tuple[int, int] = (512, 512)
    file_format: FileFormat = FileFormat.PNG
    filename_pattern: str = "render_{frame:04d}"
    use_motion_blur: bool = True
    use_gpu: bool = True
    transparent_bg: bool = False
    video_container: str = "MPEG4"  # Only used when file_format is FFMPEG
    video_codec: VideoCodec = VideoCodec.H264  # Only used when file_format is FFMPEG

class SilenceBlender:
    """Context manager to suppress Blender's noisy stdout/stderr."""
    def __enter__(self):
        self.old_stdout_fd = os.dup(1)
        self.old_stderr_fd = os.dup(2)
        self.devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.devnull_fd, 1)
        os.dup2(self.devnull_fd, 2)

    def __exit__(self, type, value, traceback):
        os.dup2(self.old_stdout_fd, 1)
        os.dup2(self.old_stderr_fd, 2)
        os.close(self.old_stdout_fd)
        os.close(self.old_stderr_fd)
        os.close(self.devnull_fd)

class Renderer:
    """The high-level interface to trigger renders."""
    def __init__(self, scene_wrapper):
        self.sw = scene_wrapper
        self.scene = scene_wrapper.scene

    def apply_config(self, config: RenderConfig):
        """Applies RenderConfig settings to the Blender scene."""
        s = self.scene
        render = s.render
        
        render.engine = config.engine.value
        render.resolution_x = config.resolution[0]
        render.resolution_y = config.resolution[1]
        render.image_settings.file_format = config.file_format.value
        render.use_motion_blur = config.use_motion_blur
        s.render.film_transparent = config.transparent_bg

        if config.engine == RenderEngine.CYCLES:
            s.cycles.samples = config.samples
            if config.use_gpu:
                s.cycles.device = 'GPU'
                # Setup Metal for Mac
                prefs = bpy.context.preferences.addons['cycles'].preferences
                prefs.compute_device_type = 'METAL'
                for d in prefs.get_devices_for_type('METAL'):
                    d.use = True
            else:
                s.cycles.device = 'CPU'

        if not os.path.exists(config.output_dir):
            os.makedirs(config.output_dir)

        if config.file_format == FileFormat.FFMPEG:
            # Configure FFmpeg settings
            render.ffmpeg.format = config.video_container
            render.ffmpeg.codec = config.video_codec.value
            render.ffmpeg.constant_rate_factor = 'MEDIUM' # Quality
            render.ffmpeg.audio_codec = 'NONE'
        
        self.config = config

    def render_frame(self, frame: int):
            """Renders a single frame after updating the scene's timeline."""
            self.sw.current_frame = frame
            filename = self.config.filename_pattern.format(frame=frame)
            
            if self.config.file_format == FileFormat.PNG:
                ext = "png"
            elif self.config.file_format == FileFormat.JPEG:
                ext = "jpg"
            elif self.config.file_format == FileFormat.OPEN_EXR:
                ext = "exr"
            else:
                ext = "png"
                
            filepath = os.path.abspath(os.path.join(self.config.output_dir, f"{filename}.{ext}"))
            self.scene.render.filepath = filepath
            with SilenceBlender():
                bpy.ops.render.render(write_still=True)
                    
            return filepath

    def render_sequence(self, start: Optional[int] = None, end: Optional[int] = None):
        """Renders a range of frames with a tqdm progress bar."""
        start_frame = start or self.scene.frame_start
        end_frame = end or self.scene.frame_end
        total_frames = end_frame - start_frame + 1

        print(f"🚀 Rendering {total_frames} frames to: {self.config.output_dir}")
        
        pbar = tqdm(total=total_frames, desc="Rendering", unit="frame")
        
        for frame in range(start_frame, end_frame + 1):
            self.render_frame(frame)
            pbar.update(1)
            
        pbar.close()
        print(f"🏁 Sequence complete.")