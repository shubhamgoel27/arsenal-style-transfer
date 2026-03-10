"""Load style presets from config."""

from pathlib import Path

import yaml


def load_styles(config_path: Path = Path("config/styles.yaml")) -> dict:
    """Load style presets from YAML config."""
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return data.get("styles", {})


def get_style_prompt(style_name: str, config_path: Path = Path("config/styles.yaml")) -> str:
    """Get the prompt for a named style."""
    styles = load_styles(config_path)
    if style_name not in styles:
        available = ", ".join(styles.keys())
        raise ValueError(f"Unknown style '{style_name}'. Available: {available}")
    return styles[style_name]["prompt"]


def list_styles(config_path: Path = Path("config/styles.yaml")) -> list[str]:
    """List available style names."""
    return list(load_styles(config_path).keys())
