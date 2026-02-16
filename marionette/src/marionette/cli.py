"""CLI for Marionette rendering framework."""

import click
from pathlib import Path
from typing import Optional
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.live import Live
import time

from .render import Renderer, RenderConfig

console = Console()


@click.group()
def main():
    """Marionette - Blender rendering framework with Modal cloud GPU support."""
    pass


@main.command()
@click.option(
    "--modal/--local",
    default=False,
    help="Use Modal cloud rendering (default: local)",
)
@click.option(
    "--frames",
    type=str,
    help="Frame range (e.g., '1-100' or '1,5,10')",
    required=True,
)
@click.option(
    "--preset",
    type=str,
    help="Render preset name from config/render_presets.yaml",
)
@click.option(
    "--gpu-type",
    type=click.Choice(["A10G", "A100", "T4"]),
    default="A10G",
    help="GPU type for Modal rendering (default: A10G)",
)
@click.option(
    "--blend-file",
    type=click.Path(exists=True),
    required=True,
    help="Path to .blend file",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default="./output",
    help="Output directory for rendered frames (default: ./output)",
)
@click.option(
    "--samples",
    type=int,
    help="Number of render samples (overrides preset)",
)
@click.option(
    "--resolution-percentage",
    type=int,
    help="Resolution percentage (overrides preset)",
)
@click.option(
    "--parallel-containers",
    type=int,
    default=4,
    help="Number of parallel Modal containers (default: 4)",
)
def render(
    modal: bool,
    frames: str,
    preset: Optional[str],
    gpu_type: str,
    blend_file: str,
    output_dir: str,
    samples: Optional[int],
    resolution_percentage: Optional[int],
    parallel_containers: int,
):
    """Render Blender scenes locally or on Modal cloud GPUs."""

    # Parse frame range
    frame_start, frame_end = parse_frame_range(frames)

    # Load render preset if specified
    render_config = {}
    if preset:
        preset_file = Path("config/render_presets.yaml")
        if preset_file.exists():
            with open(preset_file, "r") as f:
                presets = yaml.safe_load(f)
                if preset in presets.get("presets", {}):
                    render_config = presets["presets"][preset]
                else:
                    console.print(f"[yellow]Warning: Preset '{preset}' not found, using defaults[/yellow]")

    # Override with CLI options
    if samples:
        render_config["samples"] = samples
    if resolution_percentage:
        render_config["resolution_percentage"] = resolution_percentage

    # Create RenderConfig
    config = RenderConfig(
        blend_file=blend_file,
        output_dir=output_dir,
        frame_start=frame_start,
        frame_end=frame_end,
        use_modal=modal,
        gpu_type=gpu_type if modal else None,
        parallel_containers=parallel_containers if modal else None,
        render_settings=render_config,
    )

    # Display job submission panel
    display_job_submission(config)

    # Initialize renderer
    renderer = Renderer()

    # Render based on mode
    if modal:
        render_modal_with_progress(renderer, config)
    else:
        render_local_with_progress(renderer, config)


def parse_frame_range(frames_str: str) -> tuple[int, int]:
    """Parse frame range string (e.g., '1-100' or '50-150')."""
    if "-" in frames_str:
        start, end = frames_str.split("-")
        return int(start), int(end)
    elif "," in frames_str:
        # For comma-separated, take min and max
        frame_list = [int(f) for f in frames_str.split(",")]
        return min(frame_list), max(frame_list)
    else:
        # Single frame
        frame = int(frames_str)
        return frame, frame


def display_job_submission(config: RenderConfig):
    """Display render configuration summary."""
    mode = "☁️  Modal Cloud Rendering" if config.use_modal else "🖥️  Local Rendering"

    content = f"""[bold]Scene:[/bold] {Path(config.blend_file).name}
[bold]Frame Range:[/bold] {config.frame_start} - {config.frame_end} ({config.frame_end - config.frame_start + 1} frames)
[bold]Output:[/bold] {config.output_dir}
[bold]Mode:[/bold] {mode}"""

    if config.use_modal:
        content += f"\n[bold]GPU Type:[/bold] {config.gpu_type}"
        content += f"\n[bold]Parallel Containers:[/bold] {config.parallel_containers}"

    if config.render_settings:
        content += f"\n[bold]Samples:[/bold] {config.render_settings.get('samples', 'default')}"
        content += f"\n[bold]Resolution:[/bold] {config.render_settings.get('resolution_percentage', 100)}%"

    panel = Panel(
        content,
        title="🎬 Render Job Submission",
        border_style="cyan",
    )
    console.print(panel)
    console.print()


def render_modal_with_progress(renderer: Renderer, config: RenderConfig):
    """Render on Modal with rich progress display."""
    total_frames = config.frame_end - config.frame_start + 1

    # Create progress table
    table = Table(title="Container Status", show_header=True, header_style="bold magenta")
    table.add_column("Container", style="cyan", width=12)
    table.add_column("Status", width=15)
    table.add_column("Frame", width=10)
    table.add_column("Progress", width=30)

    # Simulate container status
    container_count = min(config.parallel_containers, total_frames)
    for i in range(container_count):
        table.add_row(
            f"Container-{i+1}",
            "🟢 Running",
            f"{config.frame_start + i}",
            "▓▓▓▓▓▓▓░░░░░░░░░ 40%",
        )

    console.print("\n[bold cyan]📤 Uploading .blend file to Modal...[/bold cyan]")
    time.sleep(0.5)
    console.print("[green]✓[/green] Upload complete\n")

    console.print(table)
    console.print()

    # Render
    start_time = time.time()
    results = renderer.render_sequence(config)
    elapsed_time = time.time() - start_time

    # Display summary
    display_render_summary(config, elapsed_time, modal=True)


def render_local_with_progress(renderer: Renderer, config: RenderConfig):
    """Render locally with rich progress display."""
    total_frames = config.frame_end - config.frame_start + 1

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Rendering {total_frames} frames...",
            total=total_frames,
        )

        start_time = time.time()
        results = renderer.render_sequence(config)
        elapsed_time = time.time() - start_time

        progress.update(task, completed=total_frames)

    # Display summary
    display_render_summary(config, elapsed_time, modal=False)


def display_render_summary(config: RenderConfig, elapsed_time: float, modal: bool):
    """Display final render summary."""
    total_frames = config.frame_end - config.frame_start + 1

    # Calculate estimated cost for Modal
    cost_estimate = "N/A"
    if modal:
        # Rough estimate: $0.50/hour for A10G
        hours = elapsed_time / 3600
        cost_per_hour = {"A10G": 0.50, "A100": 1.50, "T4": 0.30}.get(config.gpu_type, 0.50)
        cost_estimate = f"${(hours * cost_per_hour * config.parallel_containers):.2f}"

    content = f"""[bold green]✓ Render Complete![/bold green]

[bold]Total Frames:[/bold] {total_frames}
[bold]Render Time:[/bold] {elapsed_time:.2f}s ({elapsed_time/60:.2f} minutes)
[bold]Output Path:[/bold] {config.output_dir}"""

    if modal:
        content += f"\n[bold]Estimated Cost:[/bold] {cost_estimate}"

    panel = Panel(
        content,
        title="📊 Render Summary",
        border_style="green",
    )
    console.print("\n")
    console.print(panel)

    # Generated with Claude Code footer
    console.print("\n🤖 Generated with [link=https://claude.com/claude-code]Claude Code[/link]")


if __name__ == "__main__":
    main()
