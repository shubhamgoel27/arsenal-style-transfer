"""Assemble styled frames back into video."""

import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def frames_to_video(
    frames_dir: Path,
    output_path: Path,
    fps: int = 12,
    pattern: str = "frame_%05d.png",
) -> Path:
    """Assemble frames into a video using ffmpeg.

    Args:
        frames_dir: Directory containing the frames.
        output_path: Output video file path.
        fps: Frames per second for the output video.
        pattern: Frame filename pattern (printf-style).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / pattern),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    console.print(f"[green]Created video: {output_path}[/green]")
    return output_path


def add_audio(
    video_path: Path,
    audio_source: Path,
    output_path: Path,
) -> Path:
    """Merge audio from the original clip into the styled video."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_source),
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    console.print(f"[green]Added audio: {output_path}[/green]")
    return output_path


def create_side_by_side(
    original_video: Path,
    styled_video: Path,
    output_path: Path,
) -> Path:
    """Create a side-by-side comparison video."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(original_video),
        "-i", str(styled_video),
        "-filter_complex",
        "[0:v]scale=640:-2[left];[1:v]scale=640:-2[right];[left][right]hstack=inputs=2",
        "-c:v", "libx264",
        "-crf", "18",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    console.print(f"[green]Side-by-side: {output_path}[/green]")
    return output_path
