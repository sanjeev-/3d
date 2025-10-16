"""
Project views.
"""

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Project, Asset, Character
from .serializers import ProjectSerializer, AssetSerializer, CharacterSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Custom permission to only allow owners to edit objects."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user


class ProjectViewSet(viewsets.ModelViewSet):
    """ViewSet for Project model."""
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['get'])
    def scenes(self, request, pk=None):
        """Get all scenes for a project."""
        project = self.get_object()
        from scenes.serializers import SceneSerializer
        scenes = project.scenes.all()
        serializer = SceneSerializer(scenes, many=True)
        return Response(serializer.data)


class AssetViewSet(viewsets.ModelViewSet):
    """ViewSet for Asset model."""
    serializer_class = AssetSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        queryset = Asset.objects.filter(owner=self.request.user)
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        # Calculate file size if file is provided
        file_size = None
        if 'file' in self.request.FILES:
            file_size = self.request.FILES['file'].size

        serializer.save(owner=self.request.user, file_size=file_size)


class CharacterViewSet(viewsets.ModelViewSet):
    """ViewSet for Character model."""
    serializer_class = CharacterSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        queryset = Character.objects.filter(owner=self.request.user)
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
