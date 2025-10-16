"""
Scene app URLs.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SceneViewSet, SceneObjectViewSet, RenderJobViewSet

router = DefaultRouter()
router.register(r'scenes', SceneViewSet, basename='scene')
router.register(r'scene-objects', SceneObjectViewSet, basename='sceneobject')
router.register(r'render-jobs', RenderJobViewSet, basename='renderjob')

urlpatterns = [
    path('', include(router.urls)),
]
