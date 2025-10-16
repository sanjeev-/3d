"""
Project serializers.
"""

from rest_framework import serializers
from .models import Project, Asset, Character


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for Project model."""
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    scenes_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'owner', 'owner_username', 'title', 'description',
            'resolution_width', 'resolution_height', 'fps', 'duration_frames',
            'render_engine', 'render_samples', 'thumbnail',
            'created_at', 'updated_at', 'scenes_count'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']

    def get_scenes_count(self, obj):
        return obj.scenes.count()


class AssetSerializer(serializers.ModelSerializer):
    """Serializer for Asset model."""
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = Asset
        fields = [
            'id', 'project', 'owner', 'owner_username', 'name', 'description',
            'asset_type', 'file', 'thumbnail', 'file_size',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'file_size', 'created_at', 'updated_at']


class CharacterSerializer(serializers.ModelSerializer):
    """Serializer for Character model."""
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = Character
        fields = [
            'id', 'project', 'owner', 'owner_username', 'name', 'description',
            'blend_file', 'thumbnail', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']
