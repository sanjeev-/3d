"""Marionette - Blender rendering framework with Modal cloud GPU support."""

__version__ = "0.1.0"

from .render import Renderer, RenderConfig
from .modal_render import render_frames_remote

__all__ = ["Renderer", "RenderConfig", "render_frames_remote"]
