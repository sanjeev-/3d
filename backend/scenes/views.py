"""
Scene views.
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from projects.views import IsOwnerOrReadOnly
from .models import Scene, SceneObject, RenderJob
from .serializers import SceneSerializer, SceneObjectSerializer, RenderJobSerializer
from .services import BlenderService


class SceneViewSet(viewsets.ModelViewSet):
    """ViewSet for Scene model."""
    serializer_class = SceneSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Scene.objects.filter(project__owner=self.request.user)

    def perform_create(self, serializer):
        scene = serializer.save()
        # Initialize Blender file
        BlenderService.create_scene_blend_file(scene)

    @action(detail=True, methods=['post'])
    def add_object(self, request, pk=None):
        """Add an object to the scene."""
        scene = self.get_object()
        data = request.data.copy()
        data['scene'] = scene.id

        serializer = SceneObjectSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()

        # Update Blender file
        BlenderService.add_object_to_scene(scene, obj)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def update_object(self, request, pk=None):
        """Update an object in the scene."""
        scene = self.get_object()
        object_id = request.data.get('object_id')

        try:
            scene_object = SceneObject.objects.get(id=object_id, scene=scene)
        except SceneObject.DoesNotExist:
            return Response(
                {'error': 'Object not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SceneObjectSerializer(scene_object, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Update Blender file
        BlenderService.update_object_in_scene(scene, scene_object)

        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def render(self, request, pk=None):
        """Start a render job for the scene."""
        scene = self.get_object()

        # Create render job
        render_job = RenderJob.objects.create(
            scene=scene,
            preset=request.data.get('preset', 'medium'),
            samples=request.data.get('samples')
        )

        # Start rendering in background (would use Celery in production)
        # For now, just update status
        render_job.status = 'PENDING'
        render_job.save()

        serializer = RenderJobSerializer(render_job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SceneObjectViewSet(viewsets.ModelViewSet):
    """ViewSet for SceneObject model."""
    serializer_class = SceneObjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SceneObject.objects.filter(scene__project__owner=self.request.user)


class RenderJobViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for RenderJob model."""
    serializer_class = RenderJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RenderJob.objects.filter(scene__project__owner=self.request.user)
