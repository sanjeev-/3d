"""
Project models for movie management.
"""

from django.db import models
from django.conf import settings
import uuid


class Project(models.Model):
    """
    Represents a movie project.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects'
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Movie settings
    resolution_width = models.IntegerField(default=1920)
    resolution_height = models.IntegerField(default=1080)
    fps = models.IntegerField(default=24)
    duration_frames = models.IntegerField(default=240)

    # Render settings
    render_engine = models.CharField(
        max_length=50,
        choices=[('CYCLES', 'Cycles'), ('EEVEE', 'Eevee')],
        default='CYCLES'
    )
    render_samples = models.IntegerField(default=128)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Thumbnail
    thumbnail = models.ImageField(upload_to='project_thumbnails/', null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} ({self.owner.username})"


class Asset(models.Model):
    """
    Represents a reusable asset (models, textures, etc.).
    """
    ASSET_TYPES = [
        ('MODEL', 'Model'),
        ('TEXTURE', 'Texture'),
        ('MATERIAL', 'Material'),
        ('HDRI', 'HDRI'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='assets',
        null=True,
        blank=True  # Allow global assets
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assets'
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    asset_type = models.CharField(max_length=50, choices=ASSET_TYPES)

    # File storage
    file = models.FileField(upload_to='assets/')
    thumbnail = models.ImageField(upload_to='asset_thumbnails/', null=True, blank=True)

    # Metadata
    file_size = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.asset_type})"


class Character(models.Model):
    """
    Represents a character that can be placed in scenes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='characters',
        null=True,
        blank=True  # Allow global characters
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='characters'
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Character asset (blend file with rigged character)
    blend_file = models.FileField(upload_to='characters/')
    thumbnail = models.ImageField(upload_to='character_thumbnails/', null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
