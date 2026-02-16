"""
Demo script showing Modal cloud GPU rendering with the Marionette framework.
"""

from pathlib import Path
from marionette import Renderer, RenderConfig


def main():
    """Run a Modal cloud rendering demo."""

    # Define render configuration for Modal cloud rendering
    config = RenderConfig(
        blend_file="path/to/your/scene.blend",
        output_dir="./output/modal_render",
        frame_start=1,
        frame_end=100,
        use_modal=True,  # Enable Modal cloud rendering
        gpu_type="A10G",  # Use NVIDIA A10G GPUs
        parallel_containers=8,  # Distribute across 8 parallel containers
        render_settings={
            "engine": "CYCLES",
            "samples": 256,
            "resolution_percentage": 100,
            "denoising": True,
            "format": "PNG",
        },
    )

    # Initialize renderer
    renderer = Renderer()

    # Render the sequence on Modal
    print("Starting Modal cloud render...")
    print(f"Distributing {config.frame_end - config.frame_start + 1} frames across {config.parallel_containers} containers")
    print(f"Using {config.gpu_type} GPUs")

    results = renderer.render_sequence(config)

    # Check results
    successful = sum(1 for r in results if r.get("status") == "success")
    failed = sum(1 for r in results if r.get("status") == "error")

    print(f"\n✓ Render complete!")
    print(f"  Successful frames: {successful}")
    print(f"  Failed frames: {failed}")
    print(f"  Output directory: {config.output_dir}")


def modal_render_with_different_gpu_types():
    """Demo showing different GPU type options."""

    # High-performance render with A100 GPUs
    config_a100 = RenderConfig(
        blend_file="path/to/complex_scene.blend",
        output_dir="./output/a100_render",
        frame_start=1,
        frame_end=50,
        use_modal=True,
        gpu_type="A100",  # Use powerful A100 GPUs for complex scenes
        parallel_containers=4,
        render_settings={
            "engine": "CYCLES",
            "samples": 512,  # High sample count
            "resolution_percentage": 100,
            "denoising": True,
        },
    )

    # Budget-friendly render with T4 GPUs
    config_t4 = RenderConfig(
        blend_file="path/to/simple_scene.blend",
        output_dir="./output/t4_render",
        frame_start=1,
        frame_end=200,
        use_modal=True,
        gpu_type="T4",  # Use cost-effective T4 GPUs for simpler scenes
        parallel_containers=12,  # More containers for parallel processing
        render_settings={
            "engine": "CYCLES",
            "samples": 64,
            "resolution_percentage": 75,
            "denoising": True,
        },
    )

    renderer = Renderer()

    print("Demo: Different GPU types for different use cases")
    print("\n1. A100 render (high-quality, complex scene):")
    print(f"   GPU: {config_a100.gpu_type}, Containers: {config_a100.parallel_containers}")

    print("\n2. T4 render (cost-effective, simple scene):")
    print(f"   GPU: {config_t4.gpu_type}, Containers: {config_t4.parallel_containers}")


def modal_render_with_cli():
    """Demo showing CLI usage for Modal rendering."""

    print("\n" + "=" * 60)
    print("CLI Usage Examples")
    print("=" * 60)

    print("\nLocal rendering:")
    print("  marionette render --local \\")
    print("    --blend-file scene.blend \\")
    print("    --frames 1-30 \\")
    print("    --output-dir ./output/local")

    print("\nModal rendering with A10G GPUs:")
    print("  marionette render --modal \\")
    print("    --blend-file scene.blend \\")
    print("    --frames 1-100 \\")
    print("    --gpu-type A10G \\")
    print("    --parallel-containers 8 \\")
    print("    --output-dir ./output/modal")

    print("\nModal rendering with preset:")
    print("  marionette render --modal \\")
    print("    --blend-file scene.blend \\")
    print("    --frames 1-100 \\")
    print("    --preset high_quality \\")
    print("    --gpu-type A100 \\")
    print("    --output-dir ./output/hq_render")


if __name__ == "__main__":
    main()
    print("\n" + "=" * 60)
    modal_render_with_different_gpu_types()
    modal_render_with_cli()
