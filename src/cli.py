"""CLI for Arsenal Style Transfer pipeline."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Arsenal FC Highlight Style Transfer")
console = Console()

DATA_DIR = Path("data")


@app.command()
def highlights(
    limit: int = typer.Option(10, help="Max number of highlights to fetch"),
    download_index: int = typer.Option(None, "--download", "-d", help="Download highlight by index number"),
):
    """Browse recent Arsenal highlights and download via YouTube search."""
    from src.sourcing.scorebat import fetch_arsenal_highlights
    from src.sourcing.downloader import search_and_download

    results = fetch_arsenal_highlights(limit=limit)

    if not results:
        console.print("[yellow]No Arsenal highlights found.[/yellow]")
        raise typer.Exit()

    table = Table(title="Arsenal Highlights")
    table.add_column("#", style="dim")
    table.add_column("Match")
    table.add_column("Type")
    table.add_column("Competition")
    table.add_column("Date")

    for i, h in enumerate(results):
        table.add_row(str(i), h["match_title"][:40], h["title"][:20], h["competition"], h["date"][:10])

    console.print(table)

    if download_index is not None:
        if download_index >= len(results):
            console.print(f"[red]Invalid index {download_index}[/red]")
            raise typer.Exit(1)
        h = results[download_index]
        console.print(f"\n[bold]Searching YouTube for:[/bold] {h['search_query']}")
        try:
            path = search_and_download(
                h["search_query"],
                competition=h["competition"],
                match_name=h["match_title"],
                date=h["date"],
            )
        except RuntimeError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        console.print(f"\n[bold green]Saved to:[/bold green] {path}")
        console.print(f"[dim]Next: uv run python -m src.cli process {path}[/dim]")
    else:
        console.print("\n[bold]To download a clip:[/bold]")
        console.print("  uv run python -m src.cli highlights --download 0")


@app.command()
def download(
    query: str = typer.Argument(..., help="YouTube URL or search query"),
    output_dir: Path = typer.Option(DATA_DIR / "raw", help="Output directory"),
):
    """Download a video clip from a URL or YouTube search query."""
    from src.sourcing.downloader import download_clip, search_and_download

    try:
        if query.startswith("http://") or query.startswith("https://"):
            path = download_clip(query, output_dir=output_dir)
        else:
            console.print(f"[bold]Searching YouTube for:[/bold] {query}")
            path = search_and_download(query, output_dir=output_dir)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"\n[bold green]Saved to:[/bold green] {path}")
    console.print(f"[dim]Next: uv run python -m src.cli process {path}[/dim]")


@app.command()
def process(
    video: Path = typer.Argument(..., help="Path to video file"),
    fps: int = typer.Option(12, help="Frames per second to extract"),
    keyframe_interval: int = typer.Option(12, help="Select every Nth frame as keyframe"),
    name: str = typer.Option(None, help="Name for this clip (default: video filename)"),
):
    """Extract frames and keyframes from a video clip."""
    from src.processing.frames import extract_frames, get_video_info
    from src.processing.keyframes import select_keyframes, copy_keyframes

    clip_name = name or video.stem
    frames_dir = DATA_DIR / "frames" / clip_name
    keyframes_dir = DATA_DIR / "keyframes" / clip_name

    info = get_video_info(video)
    console.print(f"[bold]Video:[/bold] {video.name}")
    console.print(f"  Resolution: {info['width']}x{info['height']}")
    console.print(f"  Duration: {info['duration_s']:.1f}s")
    console.print(f"  Original FPS: {info['fps']:.1f}")

    frames = extract_frames(video, frames_dir, fps=fps)
    keyframes = select_keyframes(frames_dir, interval=keyframe_interval)
    copy_keyframes(keyframes, keyframes_dir)

    console.print(f"\n[bold green]All frames:[/bold green]  {frames_dir}")
    console.print(f"[bold green]Keyframes:[/bold green]   {keyframes_dir}")
    console.print(
        f"\n[dim]Tip: Upload keyframes from {keyframes_dir} to Gemini for manual style transfer,[/dim]"
        f"\n[dim]or run: uv run python -m src.cli stylize {clip_name} --style spiderverse[/dim]"
    )


@app.command()
def stylize(
    clip_name: str = typer.Argument(..., help="Name of the processed clip"),
    style: str = typer.Option("spiderverse", help="Style preset name"),
    api_key: str = typer.Option(None, envvar="GEMINI_API_KEY", help="Gemini API key"),
    use_keyframes_only: bool = typer.Option(True, help="Only stylize keyframes (recommended)"),
    model: str = typer.Option("gemini-2.0-flash-exp", help="Gemini model to use"),
):
    """Apply a style to extracted frames using Gemini API."""
    from src.stylize.gemini import stylize_keyframes
    from src.stylize.presets import get_style_prompt

    prompt = get_style_prompt(style)
    console.print(f"[bold]Style:[/bold] {style}")
    console.print(f"[bold]Prompt:[/bold] {prompt[:80]}...")

    if use_keyframes_only:
        source_dir = DATA_DIR / "keyframes" / clip_name
    else:
        source_dir = DATA_DIR / "frames" / clip_name

    if not source_dir.exists():
        console.print(f"[red]Not found: {source_dir}[/red]")
        console.print("[dim]Run 'uv run python -m src.cli process <video>' first.[/dim]")
        raise typer.Exit(1)

    frames = sorted(source_dir.glob("frame_*.png"))
    if not frames:
        console.print(f"[red]No frames found in {source_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Frames to stylize:[/bold] {len(frames)}")

    output_dir = DATA_DIR / "styled" / clip_name / style
    styled = stylize_keyframes(
        keyframes=frames,
        style_prompt=prompt,
        output_dir=output_dir,
        api_key=api_key,
        model=model,
    )

    console.print(f"\n[bold green]Styled frames:[/bold green] {output_dir}")
    console.print(f"[dim]Next: uv run python -m src.cli compose {clip_name} --style {style}[/dim]")


@app.command()
def compose(
    clip_name: str = typer.Argument(..., help="Name of the processed clip"),
    style: str = typer.Option("spiderverse", help="Style that was applied"),
    fps: int = typer.Option(12, help="Output video FPS"),
    with_audio: Path = typer.Option(None, help="Original video to extract audio from"),
    side_by_side: bool = typer.Option(False, help="Create side-by-side comparison"),
    original_video: Path = typer.Option(None, help="Original video for side-by-side"),
):
    """Compose styled frames into a video."""
    from src.compose.assembler import frames_to_video, add_audio, create_side_by_side

    styled_dir = DATA_DIR / "styled" / clip_name / style
    if not styled_dir.exists():
        console.print(f"[red]Not found: {styled_dir}[/red]")
        raise typer.Exit(1)

    output_path = DATA_DIR / "output" / f"{clip_name}_{style}.mp4"
    frames_to_video(styled_dir, output_path, fps=fps)

    if with_audio:
        final = output_path.with_name(f"{clip_name}_{style}_audio.mp4")
        add_audio(output_path, with_audio, final)
        output_path = final

    if side_by_side and original_video:
        sbs_path = output_path.with_name(f"{clip_name}_{style}_comparison.mp4")
        create_side_by_side(original_video, output_path, sbs_path)

    console.print(f"\n[bold green]Output:[/bold green] {output_path}")


@app.command()
def styles():
    """List available style presets."""
    from src.stylize.presets import load_styles

    all_styles = load_styles()

    table = Table(title="Available Styles")
    table.add_column("Name", style="bold")
    table.add_column("Prompt Preview")

    for name, cfg in all_styles.items():
        table.add_row(name, cfg["prompt"][:80] + "...")

    console.print(table)


@app.command()
def clips():
    """List local video clips and processed data."""
    from src.sourcing.downloader import list_local_clips

    all_clips = list_local_clips()

    if not all_clips:
        console.print("[yellow]No clips downloaded yet.[/yellow]")
        console.print("[dim]Run: uv run python -m src.cli highlights[/dim]")
        raise typer.Exit()

    table = Table(title="Local Clips")
    table.add_column("Path", style="bold")
    table.add_column("Size")

    for clip in all_clips:
        # Show path relative to data/raw
        try:
            rel = clip.relative_to(DATA_DIR / "raw")
        except ValueError:
            rel = clip.name
        size_mb = clip.stat().st_size / (1024 * 1024)
        table.add_row(str(rel), f"{size_mb:.1f} MB")

    console.print(table)


if __name__ == "__main__":
    app()
