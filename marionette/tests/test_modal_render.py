"""Tests for modal_render module."""

import pytest
from marionette.modal_render import RenderConfig, FrameRenderTask


def test_render_config_defaults():
    """Test RenderConfig with default values."""
    config = RenderConfig()
    assert config.engine == "CYCLES"
    assert config.device == "GPU"
    assert config.samples == 128
    assert config.resolution_percentage == 100
    assert config.denoising is True
    assert config.format == "PNG"


def test_render_config_custom():
    """Test RenderConfig with custom values."""
    config = RenderConfig(
        engine="EEVEE",
        device="CPU",
        samples=64,
        resolution_percentage=50,
        denoising=False,
        format="JPEG"
    )
    assert config.engine == "EEVEE"
    assert config.device == "CPU"
    assert config.samples == 64
    assert config.resolution_percentage == 50
    assert config.denoising is False
    assert config.format == "JPEG"


def test_frame_render_task():
    """Test FrameRenderTask creation."""
    task = FrameRenderTask(
        frame_number=42,
        blend_file_data=b"fake blend data",
        output_filename="frame_0042.png"
    )
    assert task.frame_number == 42
    assert task.blend_file_data == b"fake blend data"
    assert task.output_filename == "frame_0042.png"
    assert isinstance(task.render_config, RenderConfig)


def test_render_frames_remote_not_implemented():
    """Test that render_frames_remote raises NotImplementedError."""
    from marionette.modal_render import render_frames_remote

    with pytest.raises(NotImplementedError) as exc_info:
        render_frames_remote(
            blend_file="test.blend",
            frames=[1, 2, 3],
            output_dir="./output"
        )

    assert "task #2" in str(exc_info.value).lower()
