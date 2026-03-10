"""Style transfer using Google Gemini API (free tier)."""

import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types
from rich.console import Console

from .engine import StyleConfig, StyleEngine, StyleResult

console = Console()

DEFAULT_MODEL = "gemini-2.0-flash-exp-image-generation"


def _parse_retry_delay(error_msg: str) -> float | None:
    """Extract retry delay from a 429 error message."""
    match = re.search(r"retry in ([\d.]+)s", error_msg, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r'"retryDelay":\s*"(\d+)s"', error_msg)
    if match:
        return float(match.group(1))
    return None


class GeminiEngine(StyleEngine):
    """Gemini API style transfer engine."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        delay: float = 5.0,
        max_retries: int = 3,
    ):
        self.model = model
        self.delay = delay
        self.max_retries = max_retries
        self.client: genai.Client | None = None
        self.style_config: StyleConfig | None = None

        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "No Gemini API key found. "
                "Set GEMINI_API_KEY in .env or pass --api-key."
            )
        self._api_key = key

    def load(self, style_config: StyleConfig) -> None:
        self.style_config = style_config
        self.client = genai.Client(api_key=self._api_key)
        console.print(f"[green]Gemini engine ready (model: {self.model})[/green]")

    def stylize_frame(self, image_path: Path, output_path: Path) -> StyleResult:
        if self.client is None or self.style_config is None:
            return StyleResult(output_path, False, "Engine not loaded. Call load() first.")

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Content(
                            parts=[
                                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                                types.Part.from_text(text=self.style_config.prompt),
                            ],
                        ),
                    ],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                )

                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(output_path, "wb") as f:
                                f.write(part.inline_data.data)
                            return StyleResult(output_path, True)

                return StyleResult(output_path, False, "No image in API response")

            except Exception as e:
                error_msg = str(e)
                is_rate_limit = "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg

                if is_rate_limit and attempt < self.max_retries:
                    retry_delay = _parse_retry_delay(error_msg) or 60.0
                    console.print(
                        f"[yellow]Rate limited, waiting {retry_delay:.0f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})...[/yellow]"
                    )
                    time.sleep(retry_delay + 2)
                    continue

                return StyleResult(output_path, False, error_msg[:200])

        return StyleResult(output_path, False, "Max retries exceeded")

    def unload(self) -> None:
        self.client = None
        self.style_config = None
