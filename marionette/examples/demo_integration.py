"""
Comprehensive demo showing integration of Marionette with existing Renderer class.

This demo shows:
1. Backward compatibility with legacy Renderer methods
2. New RenderConfig-based workflow
3. Modal cloud rendering integration
4. Validation of Modal-specific options
"""

from pathlib import Path
from marionette import Renderer, RenderConfig
from pydantic import ValidationError


def demo_backward_compatibility():
    """Demo showing backward compatibility with legacy Renderer API."""
    print("=" * 60)
    print("Demo 1: Backward Compatibility")
    print("=" * 60)

    renderer = Renderer()

    # Legacy method still works (for existing code)
    print("\n✓ Legacy render_scene() method:")
    print("  renderer.render_scene(")
    print("    blend_file='scene.blend',")
    print("    output_path='./output/frame_####.png',")
    print("    frame_start=1,")
    print("    frame_end=30")
    print("  )")

    # Legacy render_frame() for single frames
    print("\n✓ Legacy render_frame() method:")
    print("  renderer.render_frame(")
    print("    blend_file='scene.blend',")
    print("    output_path='./output/frame.png',")
    print("    frame=10")
    print("  )")


def demo_local_rendering():
    """Demo showing local rendering with new RenderConfig."""
    print("\n" + "=" * 60)
    print("Demo 2: Local Rendering with RenderConfig")
    print("=" * 60)

    try:
        config = RenderConfig(
            blend_file="path/to/scene.blend",  # Update with real path
            output_dir="./output/local",
            frame_start=1,
            frame_end=30,
            use_modal=False,
            render_settings={
                "engine": "CYCLES",
                "samples": 128,
                "resolution_percentage": 100,
                "denoising": True,
                "device": "GPU",
            }
        )

        print("\n✓ Configuration created:")
        print(f"  Mode: Local")
        print(f"  Frames: {config.frame_start}-{config.frame_end}")
        print(f"  Output: {config.output_dir}")
        print(f"  Samples: {config.render_settings.get('samples')}")

        # Uncomment to actually render:
        # renderer = Renderer()
        # results = renderer.render_sequence(config)

    except FileNotFoundError as e:
        print(f"\n⚠️  Note: {e}")
        print("   (Update blend_file path to run actual render)")


def demo_modal_rendering():
    """Demo showing Modal cloud rendering."""
    print("\n" + "=" * 60)
    print("Demo 3: Modal Cloud Rendering")
    print("=" * 60)

    try:
        config = RenderConfig(
            blend_file="path/to/scene.blend",  # Update with real path
            output_dir="./output/modal",
            frame_start=1,
            frame_end=100,
            use_modal=True,
            gpu_type="A10G",
            parallel_containers=8,
            render_settings={
                "engine": "CYCLES",
                "samples": 256,
                "resolution_percentage": 100,
                "denoising": True,
            }
        )

        print("\n✓ Configuration created:")
        print(f"  Mode: Modal Cloud")
        print(f"  GPU Type: {config.gpu_type}")
        print(f"  Containers: {config.parallel_containers}")
        print(f"  Frames: {config.frame_start}-{config.frame_end}")
        print(f"  Total frames: {config.frame_end - config.frame_start + 1}")
        print(f"  Samples: {config.render_settings.get('samples')}")

        # Uncomment to actually render:
        # renderer = Renderer()
        # results = renderer.render_sequence(config)

    except FileNotFoundError as e:
        print(f"\n⚠️  Note: {e}")
        print("   (Update blend_file path to run actual render)")


def demo_validation():
    """Demo showing RenderConfig validation."""
    print("\n" + "=" * 60)
    print("Demo 4: Configuration Validation")
    print("=" * 60)

    print("\n✓ Valid configuration (Modal with GPU type):")
    try:
        config = RenderConfig(
            blend_file="path/to/scene.blend",
            output_dir="./output",
            frame_start=1,
            frame_end=100,
            use_modal=True,
            gpu_type="A10G",
        )
        print("  ✓ Configuration valid!")
    except (ValidationError, FileNotFoundError) as e:
        if isinstance(e, FileNotFoundError):
            print("  ✓ Configuration valid (file validation expected)")

    print("\n✗ Invalid configuration (GPU type without Modal):")
    try:
        config = RenderConfig(
            blend_file="path/to/scene.blend",
            output_dir="./output",
            frame_start=1,
            frame_end=100,
            use_modal=False,
            gpu_type="A10G",  # This should fail!
        )
        print("  ✗ Should have failed validation!")
    except ValidationError as e:
        print("  ✓ Validation error caught correctly:")
        print(f"    '{e.errors()[0]['msg']}'")

    print("\n✗ Invalid GPU type:")
    try:
        config = RenderConfig(
            blend_file="path/to/scene.blend",
            output_dir="./output",
            frame_start=1,
            frame_end=100,
            use_modal=True,
            gpu_type="INVALID",  # This should fail!
        )
        print("  ✗ Should have failed validation!")
    except ValidationError as e:
        print("  ✓ Validation error caught correctly:")
        print(f"    '{e.errors()[0]['msg']}'")


def demo_gpu_comparison():
    """Demo comparing different GPU types for Modal rendering."""
    print("\n" + "=" * 60)
    print("Demo 5: GPU Type Comparison")
    print("=" * 60)

    gpu_configs = {
        "T4": {
            "description": "Budget-friendly, good for simple scenes",
            "containers": 12,
            "samples": 64,
            "use_case": "Draft renders, simple animations",
        },
        "A10G": {
            "description": "Balanced performance and cost",
            "containers": 8,
            "samples": 256,
            "use_case": "Production renders, general use",
        },
        "A100": {
            "description": "High-performance, complex scenes",
            "containers": 4,
            "samples": 512,
            "use_case": "Final renders, complex lighting",
        },
    }

    for gpu_type, info in gpu_configs.items():
        print(f"\n{gpu_type}:")
        print(f"  Description: {info['description']}")
        print(f"  Recommended containers: {info['containers']}")
        print(f"  Recommended samples: {info['samples']}")
        print(f"  Use case: {info['use_case']}")


def demo_output_structure():
    """Demo showing output directory structure compatibility."""
    print("\n" + "=" * 60)
    print("Demo 6: Output Structure (VideoStitcher Compatible)")
    print("=" * 60)

    print("\nBoth local and Modal rendering produce the same structure:")
    print("\n  output_dir/")
    print("  ├── frame_0001.png")
    print("  ├── frame_0002.png")
    print("  ├── frame_0003.png")
    print("  └── ...")

    print("\nThis structure is compatible with VideoStitcher:")
    print("  from video_stitcher import VideoStitcher")
    print("  stitcher = VideoStitcher()")
    print("  stitcher.stitch('./output/modal', 'output.mp4')")


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "MARIONETTE INTEGRATION DEMO" + " " * 20 + "║")
    print("╚" + "═" * 58 + "╝")

    demo_backward_compatibility()
    demo_local_rendering()
    demo_modal_rendering()
    demo_validation()
    demo_gpu_comparison()
    demo_output_structure()

    print("\n" + "=" * 60)
    print("All demos completed!")
    print("=" * 60)
    print("\n🤖 Generated with Claude Code")
    print("   https://claude.com/claude-code\n")
