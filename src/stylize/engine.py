"""Abstract style transfer engine interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StyleConfig:
    """Configuration for a style transfer run."""
    style_name: str
    prompt: str
    negative_prompt: str = "photorealistic, blurry, low quality, watermark, text"
    denoising_strength: float = 0.65
    controlnet_conditioning_scale: float = 0.8
    num_inference_steps: int = 20
    guidance_scale: float = 7.5
    lora: str = ""
    lora_weight: float = 0.85
    trigger_words: str = ""
    seed: int | None = None


@dataclass
class StyleResult:
    """Result of stylizing a single frame."""
    output_path: Path
    success: bool
    error: str | None = None


class StyleEngine(ABC):
    """Abstract interface for style transfer backends.

    Implementations: LocalSDEngine, GeminiEngine, ReplicateEngine (future).
    """

    @abstractmethod
    def load(self, style_config: StyleConfig) -> None:
        """Load/prepare models for the given style. Called once before processing."""
        ...

    @abstractmethod
    def stylize_frame(self, image_path: Path, output_path: Path) -> StyleResult:
        """Stylize a single frame image."""
        ...

    @abstractmethod
    def unload(self) -> None:
        """Release model resources / memory."""
        ...
