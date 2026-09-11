"""Shared fixtures.

Tests under tests/blender/ need ``bpy``. It is now installable from PyPI
(``pip install bpy==5.1.1``) on Python 3.13, so those tests run in ordinary
pytest. On an interpreter without bpy they skip rather than fail.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite golden reference renders instead of comparing against them.",
    )


@pytest.fixture
def blender_scene():
    """An empty Blender scene, reset for each test that asks for one."""
    bpy = pytest.importorskip("bpy")
    bpy.ops.wm.read_homefile(use_empty=True)
    return bpy.context.scene
