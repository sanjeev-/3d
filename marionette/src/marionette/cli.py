"""
Marionette CLI - Command-line interface for cloud GPU rendering with Blender.

This module provides a Click-based CLI for rendering Blender scenes locally or
on Modal cloud infrastructure with GPU acceleration.
"""

import sys
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console

# Initialize Rich console for beautiful output
console = Console()


def load_render_preset(preset_name: str) -> dict:
    """
    Load render preset from config/render_presets.yaml.

    Args:
        preset_name: Name of the preset (e.g., 'preview', 'medium', 'high_quality', 'final')

    Returns:
        Dictionary containing render configuration

    Raises:
        click.ClickException: If preset file not found or preset name invalid
    """
    # Look for presets file in config directory
    preset_paths = [
        Path.cwd() / "config" / "render_presets.yaml",
        Path(__file__).parent.parent.parent.parent.parent / "config" / "render_presets.yaml",
        Path("/workspace/config/render_presets.yaml"),
    ]

    preset_file = None
    for path in preset_paths:
        if path.exists():
            preset_file = path
            break

    if not preset_file:
        raise click.ClickException(
            f"Render presets file not found. Searched in: {', '.join(str(p) for p in preset_paths)}"
        )

    try:
        with open(preset_file, 'r') as f:
            presets_data = yaml.safe_load(f)
    except Exception as e:
        raise click.ClickException(f"Failed to load preset file {preset_file}: {e}")

    presets = presets_data.get('presets', {})

    if preset_name not in presets:
        available = ', '.join(presets.keys())
        raise click.ClickException(
            f"Preset '{preset_name}' not found. Available presets: {available}"
        )

    return presets[preset_name]


@click.group()
@click.version_option(version="0.1.0", prog_name="marionette")
def main():
    """
    Marionette - Cloud GPU rendering for Blender.

    A powerful CLI for rendering Blender scenes locally or on Modal cloud
    infrastructure with GPU acceleration.
    """
    pass


@main.command()
@click.option(
    '--modal/--local',
    'use_modal',
    default=False,
    help='Use Modal cloud rendering (default: local)',
    show_default=True
)
@click.option(
    '--frames',
    type=str,
    default='1-10',
    help='Frame range to render (e.g., "1-120" or "1,5,10")',
    show_default=True
)
@click.option(
    '--preset',
    type=str,
    default='preview',
    help='Render quality preset (preview, medium, high_quality, final)',
    show_default=True
)
@click.option(
    '--gpu-type',
    type=click.Choice(['A10G', 'A100'], case_sensitive=False),
    default='A10G',
    help='GPU type for Modal cloud rendering (only used with --modal)',
    show_default=True
)
@click.option(
    '--blend-file',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help='Path to the .blend file to render'
)
@click.option(
    '--output-dir',
    type=click.Path(file_okay=False, path_type=Path),
    default='./output',
    help='Output directory for rendered frames',
    show_default=True
)
def render(
    use_modal: bool,
    frames: str,
    preset: str,
    gpu_type: str,
    blend_file: Path,
    output_dir: Path
):
    """
    Render Blender scenes locally or on Modal cloud infrastructure.

    Examples:

        # Local rendering with preview preset
        marionette render --local --blend-file scene.blend --frames 1-120

        # Cloud rendering with high quality preset on A100 GPU
        marionette render --modal --preset high_quality --gpu-type A100 \\
            --blend-file scene.blend --frames 1-120

        # Render specific frames only
        marionette render --local --blend-file scene.blend --frames "1,10,20,30"
    """
    try:
        # Load render preset configuration
        preset_config = load_render_preset(preset)

        # Parse frame range
        frame_start, frame_end = parse_frame_range(frames)

        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Display configuration summary
        console.print("\n[bold cyan]Marionette Render Configuration[/bold cyan]")
        console.print(f"[green]✓[/green] Mode: {'Modal Cloud' if use_modal else 'Local'}")
        console.print(f"[green]✓[/green] Blend file: {blend_file}")
        console.print(f"[green]✓[/green] Frames: {frame_start}-{frame_end}")
        console.print(f"[green]✓[/green] Preset: {preset}")
        console.print(f"[green]✓[/green] Output: {output_dir}")

        if use_modal:
            console.print(f"[green]✓[/green] GPU: {gpu_type}")
            console.print("\n[yellow]Note:[/yellow] Modal rendering requires the modal_render module (Ticket #1-2)")
            console.print("[yellow]This will be integrated in Ticket #5[/yellow]\n")
        else:
            console.print("\n[dim]Starting local render...[/dim]\n")

        # Validate preset configuration
        required_keys = ['engine', 'device', 'samples']
        for key in required_keys:
            if key not in preset_config:
                raise click.ClickException(
                    f"Invalid preset '{preset}': missing required key '{key}'"
                )

        # For now, just display what would be rendered
        # Actual rendering will be implemented in Ticket #5
        console.print("[bold green]✓ Configuration validated successfully![/bold green]")
        console.print("\n[dim]Render configuration:[/dim]")
        for key, value in preset_config.items():
            console.print(f"  {key}: {value}")

        console.print(f"\n[yellow]Ready to render {frame_end - frame_start + 1} frames[/yellow]")
        console.print("[dim]Actual rendering integration coming in Ticket #5[/dim]\n")

    except click.ClickException:
        raise
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        sys.exit(1)


def parse_frame_range(frames: str) -> tuple[int, int]:
    """
    Parse frame range string into start and end frame numbers.

    Args:
        frames: Frame range string (e.g., "1-120" or "1,5,10")

    Returns:
        Tuple of (start_frame, end_frame)

    Raises:
        click.ClickException: If frame range format is invalid
    """
    try:
        if '-' in frames:
            # Range format: "1-120"
            parts = frames.split('-')
            if len(parts) != 2:
                raise ValueError("Invalid range format")
            start, end = int(parts[0]), int(parts[1])
            if start > end:
                raise ValueError("Start frame must be <= end frame")
            return start, end
        elif ',' in frames:
            # List format: "1,5,10" - use min and max
            frame_list = [int(f.strip()) for f in frames.split(',')]
            return min(frame_list), max(frame_list)
        else:
            # Single frame
            frame = int(frames)
            return frame, frame
    except (ValueError, IndexError) as e:
        raise click.ClickException(
            f"Invalid frame range '{frames}'. Use format like '1-120' or '1,5,10'"
        )


if __name__ == '__main__':
    main()
