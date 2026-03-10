"""Scene detection to split highlight reels into individual moments."""

from pathlib import Path

from rich.console import Console
from scenedetect import detect, ContentDetector

console = Console()


def detect_scenes(
    video_path: Path,
    threshold: float = 30.0,
) -> list[tuple[float, float]]:
    """Detect scene boundaries in a video.

    Returns list of (start_seconds, end_seconds) tuples.
    """
    scene_list = detect(str(video_path), ContentDetector(threshold=threshold))

    scenes = []
    for scene in scene_list:
        start = scene[0].get_seconds()
        end = scene[1].get_seconds()
        scenes.append((start, end))

    console.print(f"[green]Detected {len(scenes)} scenes[/green]")
    return scenes


def split_video_by_scenes(
    video_path: Path,
    scenes: list[tuple[float, float]],
    output_dir: Path,
) -> list[Path]:
    """Split a video into clips based on scene boundaries."""
    import subprocess

    output_dir.mkdir(parents=True, exist_ok=True)
    clips = []

    for i, (start, end) in enumerate(scenes):
        output = output_dir / f"scene_{i:03d}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-ss", str(start),
            "-to", str(end),
            "-c", "copy",
            str(output),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        clips.append(output)

    console.print(f"[green]Split into {len(clips)} scene clips[/green]")
    return clips
