"""Load style presets from config."""

from pathlib import Path

import yaml

from .engine import StyleConfig


def load_styles(config_path: Path = Path("config/styles.yaml")) -> dict:
    """Load raw style presets from YAML config."""
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return data.get("styles", {})


def get_style_config(
    style_name: str,
    config_path: Path = Path("config/styles.yaml"),
) -> StyleConfig:
    """Get a StyleConfig for a named style."""
    styles = load_styles(config_path)
    if style_name not in styles:
        available = ", ".join(styles.keys())
        raise ValueError(f"Unknown style '{style_name}'. Available: {available}")

    s = styles[style_name]
    return StyleConfig(
        style_name=style_name,
        prompt=s["prompt"],
        negative_prompt=s.get("negative_prompt", "photorealistic, blurry, low quality, watermark, text"),
        denoising_strength=s.get("denoising_strength", 0.65),
        controlnet_conditioning_scale=s.get("controlnet_conditioning_scale", 0.8),
        num_inference_steps=s.get("num_inference_steps", 20),
        guidance_scale=s.get("guidance_scale", 7.5),
        lora=s.get("lora", ""),
        lora_weight=s.get("lora_weight", 0.85),
        trigger_words=s.get("trigger_words", ""),
        seed=s.get("seed"),
    )


def get_style_prompt(style_name: str, config_path: Path = Path("config/styles.yaml")) -> str:
    """Get the prompt for a named style (backward compat)."""
    return get_style_config(style_name, config_path).prompt


def list_styles(config_path: Path = Path("config/styles.yaml")) -> list[str]:
    """List available style names."""
    return list(load_styles(config_path).keys())
