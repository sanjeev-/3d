"""
Marionette - Cloud GPU rendering for Blender projects using Modal.
"""

__version__ = "0.1.0"

from .modal_render import render_frames_remote

__all__ = ["render_frames_remote"]
