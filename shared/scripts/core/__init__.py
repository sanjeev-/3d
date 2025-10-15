"""
Core Blender movie automation framework.
"""

from .scene_builder import MovieProject, Scene
from .renderer import Renderer
from .compositing import Compositor

__all__ = ['MovieProject', 'Scene', 'Renderer', 'Compositor']
