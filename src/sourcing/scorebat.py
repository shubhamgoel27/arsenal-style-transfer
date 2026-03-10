"""Fetch Arsenal highlight clips from the ScoreBat free API."""

import re

import httpx
from rich.console import Console

SCOREBAT_API = "https://www.scorebat.com/video-api/v3"

console = Console()


def _parse_competition(raw: str) -> str:
    """Normalize competition name from ScoreBat format.

    e.g. "ENGLAND: Premier League" -> "Premier League"
         "ENGLAND: FA Cup" -> "FA Cup"
    """
    if ":" in raw:
        return raw.split(":", 1)[1].strip()
    return raw.strip()


def _build_search_query(match_title: str, video_title: str, competition: str) -> str:
    """Build an effective YouTube search query.

    Focuses on match name + 'highlights' + official league name to
    surface real broadcast highlights, not game simulations.
    """
    # e.g. "Arsenal - Chelsea" -> "Arsenal vs Chelsea"
    match = match_title.replace(" - ", " vs ")

    # Add competition context if not already in the title
    comp_lower = competition.lower()
    parts = [match]

    if "highlight" not in video_title.lower():
        parts.append("highlights")

    # Add league name for specificity
    if "premier league" in comp_lower:
        parts.append("Premier League")
    elif "fa cup" in comp_lower:
        parts.append("FA Cup")
    elif "champions league" in comp_lower:
        parts.append("Champions League")
    elif "carabao" in comp_lower or "league cup" in comp_lower:
        parts.append("Carabao Cup")
    elif competition:
        parts.append(competition)

    return " ".join(parts)


def fetch_arsenal_highlights(limit: int = 10) -> list[dict]:
    """Fetch recent Arsenal highlights from ScoreBat.

    Returns structured match info for downloading via YouTube search.
    """
    resp = httpx.get(SCOREBAT_API, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    items = data if isinstance(data, list) else data.get("response", [])

    highlights = []
    for item in items:
        title = item.get("title", "")
        if "arsenal" not in title.lower():
            continue

        date = item.get("date", "")[:10]
        raw_competition = item.get("competitionName", item.get("competition", ""))
        competition = _parse_competition(raw_competition)

        videos = item.get("videos", [])
        for video in videos:
            video_title = video.get("title", title)
            search_query = _build_search_query(title, video_title, competition)

            highlights.append({
                "title": video_title,
                "match_title": title,
                "competition": competition,
                "date": date,
                "search_query": search_query,
            })

        if len(highlights) >= limit:
            break

    return highlights[:limit]
