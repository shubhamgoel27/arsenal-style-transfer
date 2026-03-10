"""CLI for Arsenal Style Transfer pipeline."""

import os
from pathlib import Path

import typer


def _load_dotenv():
    """Load .env file from project root if it exists."""
    env_file = Path(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(
    help="Convert Arsenal FC match highlights into animated style videos.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

DATA_DIR = Path("data")

# Alias: `uv run python -m src.cli` is verbose, so show a shorter form in help
_RUN = "uv run python -m src.cli"


@app.command()
def highlights(
    limit: int = typer.Option(10, "-n", "--limit", help="Number of highlights to fetch"),
    download_index: int = typer.Option(
        None, "-d", "--download",
        help="Immediately download highlight at this index",
    ),
):
    """Browse recent Arsenal highlights from ScoreBat and optionally download one.

    Shows a table of recent matches. Use [bold]-d INDEX[/bold] to download a specific clip
    via YouTube search. Downloaded clips are saved to data/raw/<year>/<competition>/<match>/.

    [dim]Examples:[/dim]
      [dim]Browse:    {run} highlights[/dim]
      [dim]Download:  {run} highlights -d 0[/dim]
      [dim]Limit:     {run} highlights -n 5[/dim]
    """.format(run=_RUN)
    from src.sourcing.scorebat import fetch_arsenal_highlights
    from src.sourcing.downloader import search_and_download

    results = fetch_arsenal_highlights(limit=limit)

    if not results:
        console.print("[yellow]No Arsenal highlights found on ScoreBat right now.[/yellow]")
        raise typer.Exit()

    table = Table(title="Arsenal Highlights", show_lines=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Match", min_width=20)
    table.add_column("Type", min_width=10)
    table.add_column("Competition", min_width=12)
    table.add_column("Date", width=10)

    for i, h in enumerate(results):
        table.add_row(
            str(i),
            h["match_title"],
            h["title"][:20],
            h["competition"],
            h["date"],
        )

    console.print(table)

    if download_index is not None:
        if download_index < 0 or download_index >= len(results):
            console.print(f"[red]Invalid index {download_index}. Choose 0-{len(results)-1}.[/red]")
            raise typer.Exit(1)
        h = results[download_index]
        console.print(f"\n[bold]Searching YouTube:[/bold] {h['search_query']}")
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
        _print_next_step("download", path)
    else:
        console.print(f"\n[dim]To download: {_RUN} highlights -d 0[/dim]")


@app.command()
def download(
    query: str = typer.Argument(
        ...,
        help="YouTube URL or free-text search query",
    ),
    output_dir: Path = typer.Option(
        DATA_DIR / "raw", "-o", "--output-dir",
        help="Base directory to save the clip",
    ),
    max_duration: int = typer.Option(
        600, "--max-duration",
        help="Skip YouTube results longer than this (seconds)",
    ),
    max_height: int = typer.Option(
        720, "--max-height",
        help="Max video resolution height in pixels",
    ),
):
    """Download a video clip from a YouTube URL or search query.

    Accepts either a direct YouTube link or free-text search terms.
    When searching, results are ranked by authenticity — game simulations,
    FIFA/EA FC content, and prediction videos are automatically filtered out.

    [dim]Examples:[/dim]
      [dim]URL:     {run} download "https://youtube.com/watch?v=..."[/dim]
      [dim]Search:  {run} download "Arsenal vs Chelsea highlights"[/dim]
      [dim]720p:    {run} download "Saka goal" --max-height 720[/dim]
      [dim]Short:   {run} download "Arsenal goals" --max-duration 120[/dim]
    """.format(run=_RUN)
    from src.sourcing.downloader import download_clip, search_and_download

    try:
        if query.startswith("http://") or query.startswith("https://"):
            path = download_clip(query, output_dir=output_dir, max_height=max_height)
        else:
            console.print(f"[bold]Searching YouTube:[/bold] {query}")
            path = search_and_download(
                query, output_dir=output_dir,
                max_height=max_height, max_duration=max_duration,
            )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    _print_next_step("download", path)


@app.command()
def process(
    video: Path = typer.Argument(..., help="Path to a video file (.mp4)"),
    fps: int = typer.Option(
        12, "-f", "--fps",
        help="Frames per second to extract (lower = faster, higher = smoother)",
    ),
    keyframe_interval: int = typer.Option(
        12, "-k", "--keyframe-interval",
        help="Pick every Nth frame as a keyframe for style transfer",
    ),
    name: str = typer.Option(
        None, "-n", "--name",
        help="Custom name for this clip (default: video filename stem)",
    ),
):
    """Extract frames and keyframes from a video clip.

    Pulls frames from the video at the target FPS, then selects keyframes
    at the given interval. Keyframes are the subset sent to style transfer
    (Gemini API or manual upload).

    At 12 FPS with interval 12, a 2-minute clip produces ~1440 frames and
    ~120 keyframes (1 per second).

    [dim]Examples:[/dim]
      [dim]Default:    {run} process data/raw/2026/PL/Arsenal_-_Chelsea/clip.mp4[/dim]
      [dim]Smoother:   {run} process clip.mp4 --fps 24[/dim]
      [dim]More KFs:   {run} process clip.mp4 --keyframe-interval 6[/dim]
      [dim]Custom name:{run} process clip.mp4 --name arsenal_chelsea_mar1[/dim]
    """.format(run=_RUN)
    from src.processing.frames import extract_frames, get_video_info
    from src.processing.keyframes import select_keyframes, copy_keyframes

    if not video.exists():
        console.print(f"[red]File not found: {video}[/red]")
        raise typer.Exit(1)

    clip_name = name or video.stem

    frames_dir = DATA_DIR / "frames" / clip_name
    keyframes_dir = DATA_DIR / "keyframes" / clip_name

    info = get_video_info(video)
    console.print(Panel(
        f"[bold]{video.name}[/bold]\n"
        f"  Resolution:  {info['width']}x{info['height']}\n"
        f"  Duration:    {info['duration_s']:.1f}s\n"
        f"  Original FPS: {info['fps']:.1f}\n"
        f"  Extract FPS:  {fps} ({"same" if abs(fps - info['fps']) < 1 else f"{fps / info['fps']:.1f}x"})\n"
        f"  Keyframe every: {keyframe_interval} frames",
        title="Video Info",
    ))

    frames = extract_frames(video, frames_dir, fps=fps)
    keyframes = select_keyframes(frames_dir, interval=keyframe_interval)
    copy_keyframes(keyframes, keyframes_dir)

    console.print(f"\n  All frames:  [bold]{frames_dir}[/bold] ({len(frames)} files)")
    console.print(f"  Keyframes:   [bold]{keyframes_dir}[/bold] ({len(keyframes)} files)")
    _print_next_step("process", video, clip_name=clip_name)


@app.command()
def stylize(
    clip_name: str = typer.Argument(..., help="Name of a processed clip (from 'process')"),
    style: str = typer.Option(
        "spiderverse", "-s", "--style",
        help="Style preset name (run 'styles' to see all)",
    ),
    backend: str = typer.Option(
        "local_sd", "-b", "--backend",
        help="Style engine: local_sd (runs locally on Mac), gemini (API)",
    ),
    all_frames: bool = typer.Option(
        False, "--all-frames",
        help="Stylize ALL frames instead of keyframes only (slower)",
    ),
    resolution: int = typer.Option(
        512, "-r", "--resolution",
        help="Output resolution for local_sd (512 recommended for 16GB RAM)",
    ),
    seed: int = typer.Option(
        None, "--seed",
        help="Random seed for reproducible results (local_sd only)",
    ),
):
    """Apply an animation style to keyframes.

    Uses a local Stable Diffusion pipeline (default) or Gemini API.

    [bold]local_sd[/bold] runs SD 1.5 + ControlNet + LoRA entirely on your Mac.
    Models are downloaded automatically on first run (~3GB).
    Processes ~5-15 sec/frame on M2 Pro. No API key needed.

    [bold]gemini[/bold] uses Google's Gemini API (requires GEMINI_API_KEY in .env).

    For manual style transfer, skip this command and place styled frames
    directly in data/styled/<clip_name>/<style>/ with matching filenames.

    [dim]Examples:[/dim]
      [dim]Local SD:  {run} stylize my_clip -s spiderverse[/dim]
      [dim]Gemini:    {run} stylize my_clip -s ghibli -b gemini[/dim]
      [dim]All frames:{run} stylize my_clip -s pokemon --all-frames[/dim]
      [dim]With seed: {run} stylize my_clip -s comic_book --seed 42[/dim]
    """.format(run=_RUN)
    import time
    from src.stylize.factory import create_engine
    from src.stylize.presets import get_style_config, list_styles

    try:
        style_config = get_style_config(style)
    except ValueError:
        console.print(f"[red]Unknown style '{style}'.[/red]")
        console.print(f"[dim]Available: {', '.join(list_styles())}[/dim]")
        raise typer.Exit(1)

    if seed is not None:
        style_config.seed = seed

    source_dir = DATA_DIR / ("frames" if all_frames else "keyframes") / clip_name

    if not source_dir.exists():
        console.print(f"[red]Not found: {source_dir}[/red]")
        console.print(f"[dim]Run '{_RUN} process <video>' first.[/dim]")
        raise typer.Exit(1)

    frames = sorted(source_dir.glob("frame_*.png"))
    if not frames:
        console.print(f"[red]No frames in {source_dir}[/red]")
        raise typer.Exit(1)

    output_dir = DATA_DIR / "styled" / clip_name / style

    # Check what's already done (resume support)
    already_done = sum(
        1 for f in frames
        if (output_dir / f.name).exists() and (output_dir / f.name).stat().st_size > 0
    )
    remaining = len(frames) - already_done

    console.print(Panel(
        f"  Style:      [bold]{style}[/bold]\n"
        f"  Backend:    {backend}\n"
        f"  Prompt:     {style_config.prompt[:60]}...\n"
        f"  Frames:     {len(frames)} total, {remaining} to process"
        + (f" ({already_done} done)" if already_done else "") + "\n"
        f"  Source:     {'all frames' if all_frames else 'keyframes only'}"
        + (f"\n  Resolution: {resolution}px" if backend == "local_sd" else ""),
        title="Stylize",
    ))

    if remaining == 0:
        console.print("[green]All frames already styled![/green]")
        _print_next_step("stylize", None, clip_name=clip_name, style=style)
        return

    # Create engine
    try:
        if backend == "local_sd":
            engine = create_engine("local_sd", resolution=resolution)
        elif backend == "gemini":
            engine = create_engine("gemini")
        else:
            console.print(f"[red]Unknown backend '{backend}'. Use: local_sd, gemini[/red]")
            raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    # Load style
    engine.load(style_config)

    # Process frames
    output_dir.mkdir(parents=True, exist_ok=True)
    styled_count = already_done
    failed_count = 0

    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Stylizing...", total=remaining)

        for frame in frames:
            output_path = output_dir / frame.name

            # Skip already done
            if output_path.exists() and output_path.stat().st_size > 0:
                continue

            result = engine.stylize_frame(frame, output_path)
            if result.success:
                styled_count += 1
            else:
                failed_count += 1
                console.print(f"[red]Failed {frame.name}: {result.error}[/red]")

            progress.update(task, advance=1)

            # Small delay for API backends
            if backend == "gemini":
                time.sleep(5.0)

    engine.unload()

    console.print(
        f"\n[green]Done: {styled_count}/{len(frames)} styled"
        + (f", {failed_count} failed" if failed_count else "")
        + f"[/green]\n  Output: [bold]{output_dir}[/bold]"
    )
    _print_next_step("stylize", None, clip_name=clip_name, style=style)


@app.command()
def compose(
    clip_name: str = typer.Argument(..., help="Name of the processed clip"),
    style: str = typer.Option(
        "spiderverse", "-s", "--style",
        help="Style that was applied",
    ),
    fps: int = typer.Option(12, "-f", "--fps", help="Output video FPS"),
    with_audio: Path = typer.Option(
        None, "-a", "--audio",
        help="Path to original video to extract and merge audio from",
    ),
    side_by_side: bool = typer.Option(
        False, "--side-by-side",
        help="Also create a side-by-side comparison video",
    ),
    original_video: Path = typer.Option(
        None, "--original",
        help="Path to original video (required for --side-by-side)",
    ),
):
    """Assemble styled frames back into a video file.

    Stitches the PNG frames in data/styled/<clip>/<style>/ into an mp4.
    Optionally merges audio from the original clip and/or creates a
    side-by-side comparison.

    [dim]Examples:[/dim]
      [dim]Basic:       {run} compose my_clip --style spiderverse[/dim]
      [dim]With audio:  {run} compose my_clip -s ghibli -a data/raw/.../clip.mp4[/dim]
      [dim]Comparison:  {run} compose my_clip -s pokemon --side-by-side --original clip.mp4[/dim]
    """.format(run=_RUN)
    from src.compose.assembler import frames_to_video, add_audio, create_side_by_side

    styled_dir = DATA_DIR / "styled" / clip_name / style
    if not styled_dir.exists():
        console.print(f"[red]Not found: {styled_dir}[/red]")
        console.print(f"[dim]Run '{_RUN} stylize {clip_name} --style {style}' first,[/dim]")
        console.print(f"[dim]or place styled frames manually in {styled_dir}/[/dim]")
        raise typer.Exit(1)

    n_frames = len(list(styled_dir.glob("frame_*.png")))
    if n_frames == 0:
        console.print(f"[red]No frame_*.png files found in {styled_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"  Frames: {n_frames} in {styled_dir}")

    output_path = DATA_DIR / "output" / f"{clip_name}_{style}.mp4"
    frames_to_video(styled_dir, output_path, fps=fps)

    if with_audio:
        final = output_path.with_name(f"{clip_name}_{style}_audio.mp4")
        add_audio(output_path, with_audio, final)
        output_path = final

    if side_by_side:
        if not original_video:
            console.print("[red]--original is required with --side-by-side[/red]")
            raise typer.Exit(1)
        sbs_path = output_path.with_name(f"{clip_name}_{style}_comparison.mp4")
        create_side_by_side(original_video, output_path, sbs_path)
        console.print(f"  Comparison: [bold]{sbs_path}[/bold]")

    console.print(f"\n[bold green]Output:[/bold green] {output_path}")


@app.command()
def styles():
    """List all available animation style presets."""
    from src.stylize.presets import load_styles

    all_styles = load_styles()

    table = Table(title="Available Styles", show_lines=True)
    table.add_column("Name", style="bold", min_width=12)
    table.add_column("Prompt", ratio=1)

    for name, cfg in all_styles.items():
        table.add_row(name, cfg["prompt"])

    console.print(table)
    console.print(f"\n[dim]Custom styles can be added in config/styles.yaml[/dim]")


@app.command()
def clips():
    """List all downloaded clips and their processing status."""
    from src.sourcing.downloader import list_local_clips

    all_clips = list_local_clips()

    if not all_clips:
        console.print("[yellow]No clips downloaded yet.[/yellow]")
        console.print(f"[dim]Run: {_RUN} highlights[/dim]")
        raise typer.Exit()

    table = Table(title="Downloaded Clips")
    table.add_column("Path", style="bold", ratio=1)
    table.add_column("Size", width=8, justify="right")
    table.add_column("Processed?", width=10, justify="center")

    frames_dir = DATA_DIR / "frames"
    for clip in all_clips:
        try:
            rel = clip.relative_to(DATA_DIR / "raw")
        except ValueError:
            rel = clip.name
        size_mb = clip.stat().st_size / (1024 * 1024)

        # Check if frames exist for this clip
        clip_frames_dir = frames_dir / clip.stem
        has_frames = clip_frames_dir.exists() and any(clip_frames_dir.glob("*.png"))

        table.add_row(
            str(rel),
            f"{size_mb:.1f} MB",
            "[green]yes[/green]" if has_frames else "[dim]no[/dim]",
        )

    console.print(table)


def _print_next_step(
    current_step: str,
    path: Path | None,
    clip_name: str = "",
    style: str = "spiderverse",
):
    """Print contextual next-step hints."""
    if current_step == "download":
        console.print(f"\n[bold green]Saved:[/bold green] {path}")
        console.print(f"\n[dim]Next step — extract frames:[/dim]")
        console.print(f"  {_RUN} process \"{path}\"")
    elif current_step == "process":
        console.print(f"\n[dim]Next steps:[/dim]")
        console.print(f"  [dim]Auto (Gemini API):[/dim]  {_RUN} stylize {clip_name} --style {style}")
        console.print(f"  [dim]Manual:[/dim]             Upload keyframes from data/keyframes/{clip_name}/ to Gemini")
    elif current_step == "stylize":
        console.print(f"\n[dim]Next step — compose video:[/dim]")
        console.print(f"  {_RUN} compose {clip_name} --style {style}")


if __name__ == "__main__":
    app()
