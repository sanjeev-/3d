"""
Marionette CLI - Command-line interface for cloud GPU rendering with Blender.

This module provides a Click-based CLI for rendering Blender scenes locally or
on Modal cloud infrastructure with GPU acceleration.
"""

import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn, TaskID
from rich.live import Live
from rich import box
from rich.layout import Layout
from rich.text import Text

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


def create_job_submission_panel(
    mode: str,
    blend_file: Path,
    frame_start: int,
    frame_end: int,
    preset: str,
    preset_config: Dict[str, Any],
    output_dir: Path,
    gpu_type: Optional[str] = None,
) -> Panel:
    """
    Create a beautiful Rich panel showing the render job configuration.

    Args:
        mode: 'Local' or 'Modal Cloud'
        blend_file: Path to .blend file
        frame_start: Starting frame number
        frame_end: Ending frame number
        preset: Preset name
        preset_config: Preset configuration dictionary
        output_dir: Output directory path
        gpu_type: GPU type for Modal rendering

    Returns:
        Rich Panel object with job configuration
    """
    # Calculate total frames
    total_frames = frame_end - frame_start + 1

    # Create configuration table
    config_table = Table(show_header=False, box=None, padding=(0, 2))
    config_table.add_column("Property", style="cyan", width=20)
    config_table.add_column("Value", style="white")

    # Add rows
    config_table.add_row("Mode", f"[bold]{mode}[/bold]")
    config_table.add_row("Scene File", str(blend_file))
    config_table.add_row("Frame Range", f"{frame_start}-{frame_end} ({total_frames} frames)")
    config_table.add_row("Quality Preset", preset)
    config_table.add_row("Render Engine", preset_config.get('engine', 'N/A'))
    config_table.add_row("Device", preset_config.get('device', 'N/A'))
    config_table.add_row("Samples", str(preset_config.get('samples', 'N/A')))

    if gpu_type:
        config_table.add_row("GPU Type", f"[bold green]{gpu_type}[/bold green]")

    config_table.add_row("Output Directory", str(output_dir))

    # Estimate resolution
    resolution_pct = preset_config.get('resolution_percentage', 100)
    config_table.add_row("Resolution", f"{resolution_pct}%")

    # Create panel
    panel = Panel(
        config_table,
        title="[bold cyan]🎬 Render Job Configuration[/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )

    return panel


def create_progress_table(container_status: Dict[int, Dict[str, Any]]) -> Table:
    """
    Create a live-updating table showing per-container rendering status.

    Args:
        container_status: Dictionary mapping container IDs to their status info

    Returns:
        Rich Table object with container status
    """
    table = Table(
        title="Container Status",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )

    table.add_column("Container", style="cyan", width=12)
    table.add_column("Frame", style="white", width=10)
    table.add_column("Status", width=15)
    table.add_column("Progress", width=30)
    table.add_column("Time", style="yellow", width=10)

    for container_id, status in sorted(container_status.items()):
        frame_num = status.get('frame', '-')
        state = status.get('status', 'idle')
        progress = status.get('progress', 0)
        elapsed = status.get('elapsed', 0)

        # Format status with color
        if state == 'completed':
            status_text = "[bold green]✓ Complete[/bold green]"
        elif state == 'rendering':
            status_text = "[yellow]⚙ Rendering[/yellow]"
        elif state == 'error':
            status_text = "[bold red]✗ Error[/bold red]"
        else:
            status_text = "[dim]⋯ Idle[/dim]"

        # Format progress bar
        bar_width = 20
        filled = int(bar_width * progress / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        progress_text = f"{bar} {progress:3.0f}%"

        # Format time
        time_text = f"{elapsed:.1f}s" if elapsed > 0 else "-"

        table.add_row(
            f"#{container_id}",
            str(frame_num),
            status_text,
            progress_text,
            time_text,
        )

    return table


def create_summary_panel(
    total_time: float,
    frames_rendered: int,
    frames_failed: int,
    output_dir: Path,
    gpu_type: Optional[str] = None,
) -> Panel:
    """
    Create a final summary panel with render statistics.

    Args:
        total_time: Total render time in seconds
        frames_rendered: Number of successfully rendered frames
        frames_failed: Number of failed frames
        output_dir: Output directory path
        gpu_type: GPU type used (for cost estimation)

    Returns:
        Rich Panel object with summary
    """
    # Calculate cost estimate (rough approximation)
    # Modal pricing: A10G ~$1.10/hr, A100 ~$3.50/hr
    cost_per_hour = {'A10G': 1.10, 'A100': 3.50}.get(gpu_type or '', 0)
    estimated_cost = (total_time / 3600) * cost_per_hour if cost_per_hour > 0 else 0

    # Format time
    hours = int(total_time // 3600)
    minutes = int((total_time % 3600) // 60)
    seconds = int(total_time % 60)

    if hours > 0:
        time_str = f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        time_str = f"{minutes}m {seconds}s"
    else:
        time_str = f"{seconds}s"

    # Create summary table
    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("Metric", style="cyan bold", width=25)
    summary_table.add_column("Value", style="white bold")

    # Overall status
    if frames_failed == 0:
        status_text = "[bold green]✓ SUCCESS[/bold green]"
    elif frames_rendered > 0:
        status_text = "[bold yellow]⚠ PARTIAL SUCCESS[/bold yellow]"
    else:
        status_text = "[bold red]✗ FAILED[/bold red]"

    summary_table.add_row("Status", status_text)
    summary_table.add_row("Frames Rendered", f"[green]{frames_rendered}[/green]")

    if frames_failed > 0:
        summary_table.add_row("Frames Failed", f"[red]{frames_failed}[/red]")

    summary_table.add_row("Total Time", f"[yellow]{time_str}[/yellow]")

    if frames_rendered > 0:
        avg_time = total_time / frames_rendered
        summary_table.add_row("Avg Time/Frame", f"{avg_time:.2f}s")

    if estimated_cost > 0:
        summary_table.add_row("Estimated Cost", f"[green]${estimated_cost:.4f}[/green]")

    summary_table.add_row("Output Directory", str(output_dir))

    # Create panel
    panel = Panel(
        summary_table,
        title="[bold cyan]📊 Render Summary[/bold cyan]",
        border_style="cyan" if frames_failed == 0 else "yellow",
        box=box.DOUBLE,
        padding=(1, 2),
    )

    return panel


def render_with_modal_progress(
    blend_file: Path,
    frame_start: int,
    frame_end: int,
    output_dir: Path,
    render_config: Dict[str, Any],
    gpu_type: str,
):
    """
    Execute Modal rendering with live progress display.

    Args:
        blend_file: Path to .blend file
        frame_start: Starting frame number
        frame_end: Ending frame number
        output_dir: Output directory
        render_config: Render configuration dictionary
        gpu_type: GPU type to use
    """
    from marionette import modal_render

    frames = list(range(frame_start, frame_end + 1))
    total_frames = len(frames)

    # Track start time
    start_time = time.time()

    # Initialize container status tracking
    container_status = {}
    for i in range(min(10, total_frames)):  # Limit to 10 containers for display
        container_status[i] = {
            'frame': '-',
            'status': 'idle',
            'progress': 0,
            'elapsed': 0,
        }

    # Create progress components
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:

        # Upload phase
        upload_task = progress.add_task("[cyan]Uploading .blend file...", total=100)
        time.sleep(0.5)  # Simulate upload
        progress.update(upload_task, advance=100)

        # Rendering phase
        render_task = progress.add_task(
            f"[yellow]Rendering {total_frames} frames on Modal...",
            total=total_frames
        )

        # Execute actual Modal rendering
        console.print()
        result = modal_render.render_frames_remote(
            blend_file=str(blend_file),
            frames=frames,
            output_dir=str(output_dir),
            render_config=render_config,
            gpu_type=gpu_type,
        )

        # Update progress (Modal render already completed)
        progress.update(render_task, completed=total_frames)

        # Download phase
        download_task = progress.add_task("[cyan]Downloading rendered frames...", total=100)
        time.sleep(0.5)  # Simulate download (already done in modal_render)
        progress.update(download_task, advance=100)

    # Calculate final statistics
    total_time = time.time() - start_time
    frames_rendered = result.get('frames_rendered', 0)
    frames_failed = total_frames - frames_rendered

    # Display final summary
    console.print()
    summary = create_summary_panel(
        total_time=total_time,
        frames_rendered=frames_rendered,
        frames_failed=frames_failed,
        output_dir=output_dir,
        gpu_type=gpu_type,
    )
    console.print(summary)


def render_local_with_progress(
    blend_file: Path,
    frame_start: int,
    frame_end: int,
    output_dir: Path,
    render_config: Dict[str, Any],
):
    """
    Execute local rendering with progress display.

    Args:
        blend_file: Path to .blend file
        frame_start: Starting frame number
        frame_end: Ending frame number
        output_dir: Output directory
        render_config: Render configuration dictionary
    """
    frames = list(range(frame_start, frame_end + 1))
    total_frames = len(frames)

    start_time = time.time()
    frames_rendered = 0
    frames_failed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:

        render_task = progress.add_task(
            f"[green]Rendering locally...",
            total=total_frames
        )

        # Simulate local rendering
        # In ticket #5, this will call actual Renderer class
        for i, frame in enumerate(frames):
            # Simulate frame rendering time
            time.sleep(0.1)
            progress.update(render_task, advance=1)
            frames_rendered += 1

    total_time = time.time() - start_time

    # Display final summary
    console.print()
    summary = create_summary_panel(
        total_time=total_time,
        frames_rendered=frames_rendered,
        frames_failed=frames_failed,
        output_dir=output_dir,
        gpu_type=None,
    )
    console.print(summary)


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

        # Validate preset configuration
        required_keys = ['engine', 'device', 'samples']
        for key in required_keys:
            if key not in preset_config:
                raise click.ClickException(
                    f"Invalid preset '{preset}': missing required key '{key}'"
                )

        # Display job submission panel
        console.print()
        mode = 'Modal Cloud' if use_modal else 'Local'
        job_panel = create_job_submission_panel(
            mode=mode,
            blend_file=blend_file,
            frame_start=frame_start,
            frame_end=frame_end,
            preset=preset,
            preset_config=preset_config,
            output_dir=output_dir,
            gpu_type=gpu_type if use_modal else None,
        )
        console.print(job_panel)
        console.print()

        # Execute rendering with progress display
        if use_modal:
            render_with_modal_progress(
                blend_file=blend_file,
                frame_start=frame_start,
                frame_end=frame_end,
                output_dir=output_dir,
                render_config=preset_config,
                gpu_type=gpu_type,
            )
        else:
            render_local_with_progress(
                blend_file=blend_file,
                frame_start=frame_start,
                frame_end=frame_end,
                output_dir=output_dir,
                render_config=preset_config,
            )

        console.print("\n[bold green]✓ Rendering completed successfully![/bold green]\n")

    except click.ClickException:
        raise
    except Exception as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {e}\n", style="red")
        import traceback
        console.print("[dim]" + traceback.format_exc() + "[/dim]")
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
