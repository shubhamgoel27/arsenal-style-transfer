"""Download video clips using yt-dlp with strict filtering to avoid fake/game content."""

import re
import unicodedata
from pathlib import Path

import yt_dlp
from rich.console import Console

console = Console()

DEFAULT_OUTPUT_DIR = Path("data/raw")

# Blacklist: terms that indicate fake/game/simulation content
_BLACKLIST_TERMS = [
    "fifa", "ea fc", "eafc", "ea sports fc",
    "efootball", "pes", "pro evolution",
    "football manager", " fm24", " fm25", " fm26",
    "simulation", "simulated",
    "prediction", "predicted",
    "fifa 24", "fifa 25", "fifa 26",
    "fc 24", "fc 25", "fc 26",
    "gameplay", "game play",
    "ps4", "ps5", "xbox", "nintendo",
    "4k ultra", "max settings",
    "career mode", "manager mode",
]

# Trusted channels that upload real highlights
_TRUSTED_CHANNELS = [
    "nbc sports",
    "sky sports",
    "sky sports premier league",
    "bt sport",
    "tnt sports",
    "bbc sport",
    "arsenal",
    "premier league",
    "emirates fa cup",
    "fa cup",
    "uefa champions league",
    "cbs sports golazo",
    "bein sports",
    "espn fc",
    "espn",
    "dazn",
    "optus sport",
    "football daily",
    "match of the day",
]

# Competition short names for directory structure
COMPETITION_MAP = {
    "premier league": "PL",
    "fa cup": "FA_Cup",
    "emirates fa cup": "FA_Cup",
    "carabao cup": "Carabao_Cup",
    "league cup": "Carabao_Cup",
    "efl cup": "Carabao_Cup",
    "champions league": "UCL",
    "uefa champions league": "UCL",
    "europa league": "UEL",
    "conference league": "UECL",
    "community shield": "Community_Shield",
}


def _sanitize_filename(name: str) -> str:
    """Create a clean, safe filename from a string."""
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[^\w\s-]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name[:80]
    name = name.replace(" ", "_")
    return name


def _is_fake(title: str, channel: str = "") -> bool:
    """Check if a video is likely a game/simulation, not real footage."""
    text = f"{title} {channel}".lower()
    return any(term in text for term in _BLACKLIST_TERMS)


def _is_trusted_channel(channel: str) -> bool:
    """Check if the uploader is a known official sports channel."""
    return channel.lower().strip() in _TRUSTED_CHANNELS


def _score_result(entry: dict) -> int:
    """Score a search result — higher is better.

    Prioritizes: trusted channels > real highlights > short duration.
    """
    score = 0
    title = (entry.get("title") or "").lower()
    channel = (entry.get("channel") or entry.get("uploader") or "").lower()
    duration = entry.get("duration") or 0
    view_count = entry.get("view_count") or 0

    # Hard reject fake content
    if _is_fake(title, channel):
        return -1000

    # Trusted channel is the strongest signal
    if _is_trusted_channel(channel):
        score += 500

    # Title signals for real highlights
    highlight_terms = ["highlight", "goal", "save", "assist", "match day", "extended"]
    for term in highlight_terms:
        if term in title:
            score += 50

    # Official-sounding terms
    if any(t in title for t in ["premier league", "fa cup", "ucl", "champions league"]):
        score += 30

    # Prefer reasonable duration (1-10 min is ideal for highlights)
    if 30 <= duration <= 600:
        score += 100
    elif 600 < duration <= 900:
        score += 50

    # View count as a quality signal (popular = more likely real)
    if view_count > 100_000:
        score += 80
    elif view_count > 10_000:
        score += 40
    elif view_count > 1_000:
        score += 10

    return score


def _resolve_output_dir(
    base_dir: Path,
    competition: str = "",
    match_name: str = "",
    date: str = "",
) -> Path:
    """Build structured output directory: base/year/competition/match_name/"""
    year = date[:4] if date else "unknown"

    comp_short = "Other"
    comp_lower = competition.lower()
    for key, short in COMPETITION_MAP.items():
        if key in comp_lower:
            comp_short = short
            break

    match_dir = _sanitize_filename(match_name) if match_name else "unknown"

    output_dir = base_dir / year / comp_short / match_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _base_opts(output_dir: Path, max_height: int = 720) -> dict:
    """Shared yt-dlp options."""
    return {
        "format": f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]",
        "merge_output_format": "mp4",
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "noprogress": False,
    }


def _find_downloaded_file(output_dir: Path, video_id: str) -> Path:
    """Find the final downloaded mp4 by video ID."""
    expected = output_dir / f"{video_id}.mp4"
    if expected.exists():
        return expected

    mp4s = sorted(output_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if mp4s:
        return mp4s[0]

    raise FileNotFoundError(f"Downloaded file not found for video {video_id} in {output_dir}")


def _rename_to_clean(file_path: Path, title: str) -> Path:
    """Rename downloaded file from video ID to a clean title-based name."""
    clean_name = _sanitize_filename(title)
    new_path = file_path.parent / f"{clean_name}.mp4"

    counter = 1
    while new_path.exists() and new_path != file_path:
        new_path = file_path.parent / f"{clean_name}_{counter}.mp4"
        counter += 1

    if new_path != file_path:
        file_path.rename(new_path)
    return new_path


def download_clip(
    url: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    max_height: int = 720,
    competition: str = "",
    match_name: str = "",
    date: str = "",
) -> Path:
    """Download a video clip from a direct URL.

    If competition/match_name/date are provided, organizes into subdirectories.
    """
    if competition or match_name:
        output_dir = _resolve_output_dir(output_dir, competition, match_name, date)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    opts = _base_opts(output_dir, max_height)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            raise RuntimeError(f"yt-dlp returned no info for: {url}")

        video_id = info.get("id", "unknown")
        title = info.get("title", video_id)

        result = _find_downloaded_file(output_dir, video_id)
        result = _rename_to_clean(result, title)

        console.print(f"[green]Downloaded:[/green] {result}")
        return result


def search_and_download(
    query: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    max_height: int = 720,
    max_duration: int = 600,
    competition: str = "",
    match_name: str = "",
    date: str = "",
) -> Path:
    """Search YouTube, filter out fakes, and download the best real highlight.

    Searches for 15 results, scores them by authenticity, and downloads the best.
    """
    if competition or match_name:
        output_dir = _resolve_output_dir(output_dir, competition, match_name, date)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    opts = _base_opts(output_dir, max_height)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch15:{query}", download=False)
        entries = [e for e in info.get("entries", []) if e is not None]

        if not entries:
            raise RuntimeError(
                f"No YouTube results found for: {query}\n"
                f"Try a different search query or provide a direct YouTube URL."
            )

        # Score and sort — best first
        scored = [(e, _score_result(e)) for e in entries]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Log what we're filtering
        rejected = [(e, s) for e, s in scored if s < 0]
        if rejected:
            names = [e.get("title", "?")[:50] for e, _ in rejected]
            console.print(f"[dim]Filtered out {len(rejected)} fake/game results: {', '.join(names)}[/dim]")

        # Keep only non-negative scores
        valid = [(e, s) for e, s in scored if s >= 0]
        if not valid:
            raise RuntimeError(
                f"All results for '{query}' appear to be game simulations or fake content.\n"
                f"Try providing a direct YouTube URL to a real highlight video."
            )

        # Prefer results under max_duration among the top scored
        short_valid = [(e, s) for e, s in valid if (e.get("duration") or 0) <= max_duration]
        if short_valid:
            valid = short_valid
        else:
            console.print(f"[yellow]No results under {max_duration}s, using best scored result[/yellow]")

        entry, score = valid[0]
        video_url = entry.get("webpage_url") or entry.get("url")
        title = entry.get("title", "unknown")
        channel = entry.get("channel") or entry.get("uploader") or "unknown"
        duration = entry.get("duration") or 0

        console.print(f"[bold]Found:[/bold] {title}")
        console.print(f"[dim]  Channel: {channel} | Duration: {duration}s | Score: {score}[/dim]")
        console.print(f"[dim]  {video_url}[/dim]")

        # Download
        ydl.extract_info(video_url, download=True)

        video_id = entry.get("id", "unknown")
        result = _find_downloaded_file(output_dir, video_id)
        result = _rename_to_clean(result, title)

        console.print(f"[green]Downloaded:[/green] {result}")
        return result


def list_local_clips(clip_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    """List all mp4 files in the clips directory (recursive)."""
    if not clip_dir.exists():
        return []
    return sorted(clip_dir.rglob("*.mp4"))
