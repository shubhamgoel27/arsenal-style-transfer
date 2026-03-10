"""Local Stable Diffusion 1.5 + ControlNet + LoRA engine for Apple Silicon (MPS)."""

import gc
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from rich.console import Console

from .engine import StyleConfig, StyleEngine, StyleResult

console = Console()

DEFAULT_BASE_MODEL = "stable-diffusion-v1-5/stable-diffusion-v1-5"
DEFAULT_CONTROLNET = "lllyasviel/control_v11p_sd15_canny"
DEFAULT_RESOLUTION = 512
LORA_DIR = Path("models/loras")


class LocalSDEngine(StyleEngine):
    """SD 1.5 img2img + ControlNet Canny + LoRA on MPS (Apple Silicon).

    Uses float32 on MPS (avoids fp16 NaN issues in VAE decode).
    Fits in ~6GB unified memory. Processes one frame at a time.
    """

    def __init__(
        self,
        base_model: str = DEFAULT_BASE_MODEL,
        controlnet_model: str = DEFAULT_CONTROLNET,
        lora_dir: Path = LORA_DIR,
        resolution: int = DEFAULT_RESOLUTION,
    ):
        self.base_model = base_model
        self.controlnet_model = controlnet_model
        self.lora_dir = lora_dir
        self.resolution = resolution
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.pipe = None
        self.style_config: StyleConfig | None = None
        self._warmed_up = False

    def load(self, style_config: StyleConfig) -> None:
        """Load the SD pipeline with ControlNet and optional LoRA."""
        from diffusers import (
            ControlNetModel,
            StableDiffusionControlNetImg2ImgPipeline,
            UniPCMultistepScheduler,
        )

        self.style_config = style_config

        # Use float32 on MPS to avoid NaN issues with fp16 VAE decode.
        # SD 1.5 + ControlNet in fp32 fits in ~6GB, well within 16GB unified memory.
        dtype = torch.float32 if self.device == "mps" else torch.float16

        console.print(f"[dim]Loading ControlNet: {self.controlnet_model}[/dim]")
        controlnet = ControlNetModel.from_pretrained(
            self.controlnet_model,
            torch_dtype=dtype,
        )

        console.print(f"[dim]Loading base model: {self.base_model}[/dim]")
        self.pipe = StableDiffusionControlNetImg2ImgPipeline.from_pretrained(
            self.base_model,
            controlnet=controlnet,
            torch_dtype=dtype,
            safety_checker=None,
            requires_safety_checker=False,
        )

        # Fast scheduler — 20 steps is plenty
        self.pipe.scheduler = UniPCMultistepScheduler.from_config(
            self.pipe.scheduler.config
        )

        # Load LoRA if specified
        if style_config.lora:
            lora_path = self.lora_dir / style_config.lora
            if lora_path.exists():
                console.print(f"[dim]Loading LoRA: {style_config.lora}[/dim]")
                self.pipe.load_lora_weights(
                    str(lora_path.parent),
                    weight_name=lora_path.name,
                )
            else:
                console.print(
                    f"[yellow]LoRA not found: {lora_path}. "
                    f"Running without LoRA (prompt-only stylization).[/yellow]"
                )

        # Memory optimization for 16GB Apple Silicon
        self.pipe.enable_attention_slicing()
        self.pipe.enable_vae_tiling()

        # Move to device
        self.pipe = self.pipe.to(self.device)

        console.print(f"[green]Pipeline loaded on {self.device}[/green]")

        # Warmup pass — primes MPS compilation cache
        if not self._warmed_up:
            self._warmup()
            self._warmed_up = True

    def _warmup(self):
        """Run a tiny dummy inference to prime the MPS shader cache."""
        console.print("[dim]Warming up MPS (first run is slow, subsequent runs are fast)...[/dim]")
        dummy_img = Image.new("RGB", (self.resolution, self.resolution), "black")
        dummy_canny = Image.new("L", (self.resolution, self.resolution), "black")
        try:
            self.pipe(
                prompt="test",
                image=dummy_img,
                control_image=dummy_canny,
                num_inference_steps=1,
                strength=0.5,
                guidance_scale=1.0,
                output_type="pil",
            )
        except Exception:
            pass  # warmup failure is non-fatal
        if self.device == "mps":
            torch.mps.empty_cache()

    def _extract_canny(self, image: Image.Image) -> Image.Image:
        """Extract Canny edges from an image."""
        img_array = np.array(image)
        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        edges = cv2.Canny(gray, 100, 200)
        return Image.fromarray(edges)

    def stylize_frame(self, image_path: Path, output_path: Path) -> StyleResult:
        """Stylize a single frame with SD 1.5 + ControlNet + LoRA."""
        if self.pipe is None or self.style_config is None:
            return StyleResult(output_path, False, "Pipeline not loaded. Call load() first.")

        try:
            # Load and resize source image
            source = Image.open(image_path).convert("RGB")
            source = source.resize(
                (self.resolution, self.resolution), Image.LANCZOS
            )

            # Extract canny edges for ControlNet
            canny = self._extract_canny(source)
            canny_rgb = Image.fromarray(
                cv2.cvtColor(np.array(canny), cv2.COLOR_GRAY2RGB)
            )

            # Build prompt with trigger words
            cfg = self.style_config
            prompt = cfg.prompt
            if cfg.trigger_words:
                prompt = f"{cfg.trigger_words}, {prompt}"

            # Generate
            generator = None
            if cfg.seed is not None:
                generator = torch.Generator(device=self.device).manual_seed(cfg.seed)

            result = self.pipe(
                prompt=prompt,
                negative_prompt=cfg.negative_prompt,
                image=source,
                control_image=canny_rgb,
                strength=cfg.denoising_strength,
                controlnet_conditioning_scale=cfg.controlnet_conditioning_scale,
                num_inference_steps=cfg.num_inference_steps,
                guidance_scale=cfg.guidance_scale,
                generator=generator,
                output_type="pil",
            )

            # Save
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result.images[0].save(output_path)

            # Free MPS memory
            if self.device == "mps":
                torch.mps.empty_cache()

            return StyleResult(output_path, True)

        except Exception as e:
            if self.device == "mps":
                torch.mps.empty_cache()
            return StyleResult(output_path, False, str(e))

    def unload(self) -> None:
        """Release the pipeline and free memory."""
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
        self.style_config = None
        gc.collect()
        if self.device == "mps":
            torch.mps.empty_cache()
        console.print("[dim]Pipeline unloaded[/dim]")
