"""Skip this whole directory when bpy is unavailable."""

import pytest

pytest.importorskip("bpy", reason="requires bpy (pip install bpy==5.1.1 on Python 3.13)")
