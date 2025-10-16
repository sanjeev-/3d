"""
Project app URLs.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, AssetViewSet, CharacterViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'assets', AssetViewSet, basename='asset')
router.register(r'characters', CharacterViewSet, basename='character')

urlpatterns = [
    path('', include(router.urls)),
]
