"""Select keyframes for style transfer."""

from pathlib import Path

from rich.console import Console

console = Console()


def select_keyframes(
    frames_dir: Path,
    interval: int = 12,
) -> list[Path]:
    """Select every Nth frame as a keyframe.

    Args:
        frames_dir: Directory containing extracted frames.
        interval: Select every Nth frame (e.g., 12 = 1 keyframe per second at 12 FPS).

    Returns list of keyframe paths.
    """
    all_frames = sorted(frames_dir.glob("frame_*.png"))

    keyframes = [f for i, f in enumerate(all_frames) if i % interval == 0]

    console.print(
        f"[green]Selected {len(keyframes)} keyframes from {len(all_frames)} frames "
        f"(every {interval}th frame)[/green]"
    )
    return keyframes


def copy_keyframes(
    keyframes: list[Path],
    output_dir: Path,
) -> list[Path]:
    """Copy keyframes to a separate directory for easy access/upload."""
    import shutil

    output_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for kf in keyframes:
        dest = output_dir / kf.name
        shutil.copy2(kf, dest)
        copied.append(dest)

    console.print(f"[green]Copied {len(copied)} keyframes to {output_dir}[/green]")
    return copied
