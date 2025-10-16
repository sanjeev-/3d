"""
Scene serializers.
"""

from rest_framework import serializers
from .models import Scene, SceneObject, RenderJob


class SceneObjectSerializer(serializers.ModelSerializer):
    """Serializer for SceneObject model."""

    class Meta:
        model = SceneObject
        fields = [
            'id', 'scene', 'object_type', 'name',
            'character', 'asset',
            'position_x', 'position_y', 'position_z',
            'rotation_x', 'rotation_y', 'rotation_z',
            'scale_x', 'scale_y', 'scale_z',
            'properties', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SceneSerializer(serializers.ModelSerializer):
    """Serializer for Scene model."""
    project_title = serializers.CharField(source='project.title', read_only=True)
    objects = SceneObjectSerializer(many=True, read_only=True)
    duration_frames = serializers.ReadOnlyField()

    class Meta:
        model = Scene
        fields = [
            'id', 'project', 'project_title', 'name', 'description',
            'frame_start', 'frame_end', 'duration_frames', 'order',
            'blend_file', 'thumbnail', 'camera_name',
            'blend_file_version', 'objects',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'blend_file', 'created_at', 'updated_at']


class RenderJobSerializer(serializers.ModelSerializer):
    """Serializer for RenderJob model."""
    scene_name = serializers.CharField(source='scene.name', read_only=True)

    class Meta:
        model = RenderJob
        fields = [
            'id', 'scene', 'scene_name', 'status', 'preset', 'samples',
            'progress', 'current_frame', 'output_directory', 'final_video',
            'started_at', 'completed_at', 'error_message',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'progress', 'current_frame',
            'started_at', 'completed_at', 'created_at', 'updated_at'
        ]
