"""
Demo script showing local rendering with the Marionette framework.
"""

from pathlib import Path
from marionette import Renderer, RenderConfig


def main():
    """Run a local rendering demo."""

    # Define render configuration for local rendering
    config = RenderConfig(
        blend_file="path/to/your/scene.blend",
        output_dir="./output/local_render",
        frame_start=1,
        frame_end=30,
        use_modal=False,  # Use local rendering
        render_settings={
            "engine": "CYCLES",
            "samples": 128,
            "resolution_percentage": 50,
            "denoising": True,
            "device": "GPU",  # Use local GPU if available
            "format": "PNG",
        },
    )

    # Initialize renderer
    renderer = Renderer()

    # Render the sequence
    print("Starting local render...")
    results = renderer.render_sequence(config)

    if results[0] == 0:
        print(f"✓ Render complete! Frames saved to {config.output_dir}")
    else:
        print(f"✗ Render failed with code {results[0]}")


if __name__ == "__main__":
    main()
