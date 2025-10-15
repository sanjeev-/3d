"""
Scene builder and movie project management.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any


class Scene:
    """Represents a single scene in a movie."""

    def __init__(self, name: str, blend_file: str, frame_range: List[int],
                 config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.blend_file = blend_file
        self.frame_start = frame_range[0]
        self.frame_end = frame_range[1]
        self.config = config or {}

    def __repr__(self):
        return f"Scene('{self.name}', frames={self.frame_start}-{self.frame_end})"


class MovieProject:
    """
    Main class for managing Blender movie projects.

    Loads movie definitions from YAML and provides high-level API
    for rendering, compositing, and exporting.
    """

    def __init__(self, definition_path: str):
        """
        Initialize a movie project from a definition file.

        Args:
            definition_path: Path to the movie definition YAML file
        """
        self.definition_path = Path(definition_path)
        self.project_dir = self.definition_path.parent
        self.definition = self._load_definition()
        self.scenes = self._parse_scenes()

    def _load_definition(self) -> Dict[str, Any]:
        """Load and parse the YAML definition file."""
        with open(self.definition_path, 'r') as f:
            return yaml.safe_load(f)

    def _parse_scenes(self) -> List[Scene]:
        """Parse scene definitions into Scene objects."""
        scenes = []
        for scene_data in self.definition.get('scenes', []):
            scene = Scene(
                name=scene_data['name'],
                blend_file=str(self.project_dir / scene_data['blend_file']),
                frame_range=scene_data['frame_range'],
                config=scene_data.get('config', {})
            )
            scenes.append(scene)
        return scenes

    @property
    def movie_config(self) -> Dict[str, Any]:
        """Get movie-level configuration."""
        return self.definition.get('movie', {})

    @property
    def render_config(self) -> Dict[str, Any]:
        """Get render configuration."""
        return self.definition.get('render', {})

    @property
    def output_config(self) -> Dict[str, Any]:
        """Get output configuration."""
        return self.definition.get('output', {})

    @property
    def assets_config(self) -> Dict[str, Any]:
        """Get assets configuration."""
        return self.definition.get('assets', {})

    def get_scene(self, name: str) -> Optional[Scene]:
        """Get a scene by name."""
        for scene in self.scenes:
            if scene.name == name:
                return scene
        return None

    def get_output_path(self, relative: bool = False) -> Path:
        """
        Get the output path for final renders.

        Args:
            relative: If True, return path relative to project dir
        """
        output_path = self.output_config.get('final_video', 'renders/final/output.mp4')
        path = self.project_dir / output_path
        return Path(output_path) if relative else path

    def get_frames_dir(self, scene_name: Optional[str] = None) -> Path:
        """Get the directory for rendered frames."""
        if scene_name:
            return self.project_dir / 'renders' / 'frames' / scene_name
        return self.project_dir / 'renders' / 'frames'

    def setup_output_directories(self):
        """Create necessary output directories."""
        # Create frames directory for each scene
        for scene in self.scenes:
            frames_dir = self.get_frames_dir(scene.name)
            frames_dir.mkdir(parents=True, exist_ok=True)

            # Create .gitkeep files
            (frames_dir / '.gitkeep').touch()

        # Create final output directory
        final_dir = self.get_output_path().parent
        final_dir.mkdir(parents=True, exist_ok=True)
        (final_dir / '.gitkeep').touch()

    def validate(self) -> List[str]:
        """
        Validate the project configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required fields
        if not self.movie_config:
            errors.append("Missing 'movie' section in definition")

        if not self.scenes:
            errors.append("No scenes defined")

        # Check blend files exist
        for scene in self.scenes:
            blend_path = Path(scene.blend_file)
            if not blend_path.exists():
                errors.append(f"Blend file not found: {blend_path}")

        return errors

    def __repr__(self):
        title = self.movie_config.get('title', 'Untitled')
        return f"MovieProject('{title}', {len(self.scenes)} scenes)"
