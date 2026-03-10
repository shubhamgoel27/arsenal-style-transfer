"""Style transfer using Google Gemini API (free tier)."""

import base64
import time
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image
from rich.console import Console
from rich.progress import track

console = Console()


def _load_image_bytes(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def stylize_keyframe(
    client: genai.Client,
    image_path: Path,
    style_prompt: str,
    output_path: Path,
    model: str = "gemini-2.0-flash-exp",
) -> Path | None:
    """Stylize a single keyframe using Gemini image generation.

    Returns the output path on success, None on failure.
    """
    image_bytes = _load_image_bytes(image_path)

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    types.Part.from_text(style_prompt),
                ],
            ),
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    # Extract generated image from response
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(part.inline_data.data)
            return output_path

    console.print(f"[yellow]Warning: No image in response for {image_path.name}[/yellow]")
    return None


def stylize_keyframes(
    keyframes: list[Path],
    style_prompt: str,
    output_dir: Path,
    api_key: str | None = None,
    model: str = "gemini-2.0-flash-exp",
    delay_seconds: float = 4.5,
) -> list[Path]:
    """Stylize a batch of keyframes using Gemini.

    Free tier limit is ~15 RPM, so we add a delay between requests.
    """
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    output_dir.mkdir(parents=True, exist_ok=True)

    styled = []
    for kf in track(keyframes, description="Stylizing keyframes..."):
        output_path = output_dir / kf.name
        result = stylize_keyframe(client, kf, style_prompt, output_path, model=model)
        if result:
            styled.append(result)
        else:
            console.print(f"[red]Failed: {kf.name}[/red]")

        # Rate limit: free tier is ~15 RPM
        time.sleep(delay_seconds)

    console.print(f"[green]Stylized {len(styled)}/{len(keyframes)} keyframes[/green]")
    return styled
