"""Keep bpy-only suites out of plain pytest runs.

Tests under tests/blender/ need Blender's interpreter. Everything else in this
package is pure and runs in the project venv.
"""

collect_ignore_glob = ["blender/*"]
