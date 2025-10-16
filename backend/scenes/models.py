"""
Scene models for movie scene management.
"""

from django.db import models
from django.conf import settings
from projects.models import Project, Asset, Character
import uuid
import os


def scene_blend_file_path(instance, filename):
    """Generate path for scene blend files."""
    return f"blender_files/projects/{instance.project.id}/scenes/{instance.id}.blend"


class Scene(models.Model):
    """
    Represents a scene in a movie project.
    Each scene has an associated Blender file.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='scenes'
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Frame range within the project
    frame_start = models.IntegerField(default=1)
    frame_end = models.IntegerField(default=120)

    # Order in the movie
    order = models.IntegerField(default=0)

    # Blender file (source of truth)
    blend_file = models.FileField(upload_to=scene_blend_file_path, null=True, blank=True)

    # Preview/thumbnail
    thumbnail = models.ImageField(upload_to='scene_thumbnails/', null=True, blank=True)

    # Camera settings
    camera_name = models.CharField(max_length=100, default='Camera')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Blender file version tracking
    blend_file_version = models.IntegerField(default=1)

    class Meta:
        ordering = ['project', 'order']
        unique_together = [['project', 'name']]

    def __str__(self):
        return f"{self.project.title} - {self.name}"

    @property
    def duration_frames(self):
        """Calculate duration in frames."""
        return self.frame_end - self.frame_start + 1


class SceneObject(models.Model):
    """
    Represents an object (character, asset, etc.) placed in a scene.
    """
    OBJECT_TYPES = [
        ('CHARACTER', 'Character'),
        ('ASSET', 'Asset'),
        ('LIGHT', 'Light'),
        ('CAMERA', 'Camera'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scene = models.ForeignKey(
        Scene,
        on_delete=models.CASCADE,
        related_name='objects'
    )

    object_type = models.CharField(max_length=50, choices=OBJECT_TYPES)
    name = models.CharField(max_length=255)

    # References to characters or assets
    character = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scene_instances'
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scene_instances'
    )

    # Transform data (position, rotation, scale)
    position_x = models.FloatField(default=0.0)
    position_y = models.FloatField(default=0.0)
    position_z = models.FloatField(default=0.0)

    rotation_x = models.FloatField(default=0.0)
    rotation_y = models.FloatField(default=0.0)
    rotation_z = models.FloatField(default=0.0)

    scale_x = models.FloatField(default=1.0)
    scale_y = models.FloatField(default=1.0)
    scale_z = models.FloatField(default=1.0)

    # Additional properties (JSON field for flexibility)
    properties = models.JSONField(default=dict, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scene', 'created_at']

    def __str__(self):
        return f"{self.name} in {self.scene.name}"


class RenderJob(models.Model):
    """
    Represents a render job for a scene.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RENDERING', 'Rendering'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scene = models.ForeignKey(
        Scene,
        on_delete=models.CASCADE,
        related_name='render_jobs'
    )

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='PENDING')

    # Render settings
    preset = models.CharField(max_length=50, default='medium')
    samples = models.IntegerField(null=True, blank=True)

    # Progress tracking
    progress = models.FloatField(default=0.0)  # 0-100
    current_frame = models.IntegerField(null=True, blank=True)

    # Output
    output_directory = models.CharField(max_length=500, blank=True)
    final_video = models.FileField(upload_to='renders/', null=True, blank=True)

    # Metadata
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Render {self.scene.name} - {self.status}"
