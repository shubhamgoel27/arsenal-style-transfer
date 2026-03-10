"""Extract frames from video clips."""

import subprocess
from pathlib import Path

import cv2
from rich.console import Console

console = Console()


def extract_frames(
    video_path: Path,
    output_dir: Path,
    fps: int = 12,
) -> list[Path]:
    """Extract frames from a video at the specified FPS.

    Uses ffmpeg for speed and reliability.
    Returns list of extracted frame paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    pattern = output_dir / "frame_%05d.png"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        str(pattern),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    frames = sorted(output_dir.glob("frame_*.png"))
    console.print(f"[green]Extracted {len(frames)} frames at {fps} FPS[/green]")
    return frames


def get_video_info(video_path: Path) -> dict:
    """Get basic video metadata."""
    cap = cv2.VideoCapture(str(video_path))
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "duration_s": cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1),
    }
    cap.release()
    return info
