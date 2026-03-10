# Arsenal Style Transfer

Convert Arsenal FC match highlights into different animation styles — Spiderverse ink-splatter, Pokemon anime, Studio Ghibli, comic book, and more.

## How it works

```
[Source Clips] → [Extract Frames] → [Style Transfer] → [Compose Video]
     |                 |                   |                   |
  yt-dlp           FFmpeg @ 12fps     Gemini API          FFmpeg
  ScoreBat API     Scene detection    or manual upload     + audio merge
  Local files      Keyframe selection                      + side-by-side
```

1. **Source** a clip — download from a URL, fetch from ScoreBat, or drop an mp4 locally
2. **Process** — extract frames at 12 FPS, detect scenes, select keyframes (every 12th frame)
3. **Stylize** — run keyframes through Gemini (API or manual upload) to apply an animation style
4. **Compose** — stitch styled frames back into a video, optionally with audio and side-by-side comparison

## Available styles

| Style | Description |
|---|---|
| `spiderverse` | Spider-Verse ink splatter, halftone dots, bold outlines |
| `pokemon` | Flat cel-shaded anime, bright palette |
| `ghibli` | Soft watercolor, warm lighting, painterly |
| `comic_book` | Thick ink outlines, dramatic shadows, action lines |
| `pixel_art` | 16-bit retro game aesthetic |
| `ukiyo_e` | Japanese woodblock print |

Custom styles can be added in `config/styles.yaml`.

## Setup

### Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) installed and on PATH
- [uv](https://docs.astral.sh/uv/) for dependency management

### Install

```bash
cd arsenal-style-transfer
uv sync
```

### Gemini API key (optional, for automated stylization)

Get a free API key from https://aistudio.google.com/apikey and set it:

```bash
export GEMINI_API_KEY=your_key_here
```

The free tier gives ~15 requests/minute which is plenty for keyframe-based stylization.

## Usage

All commands are run from the project root with `uv run python -m src.cli`.

### 1. Get a clip

**Option A** — Download from a URL:

```bash
uv run python -m src.cli download "https://www.youtube.com/watch?v=..."
```

**Option B** — Fetch Arsenal highlights from ScoreBat:

```bash
uv run python -m src.cli highlights
```

**Option C** — Drop an mp4 directly into `data/raw/`.

### 2. Process the clip

Extract frames and keyframes:

```bash
uv run python -m src.cli process data/raw/my_clip.mp4
```

Options:

```
--fps 12                  Frames per second to extract (default: 12)
--keyframe-interval 12    Select every Nth frame as keyframe (default: 12)
--name my_clip            Custom name for the clip (default: filename)
```

This creates:
- `data/frames/<name>/` — all extracted frames
- `data/keyframes/<name>/` — keyframes only (subset for style transfer)

### 3. Apply a style

#### Automated (Gemini API)

```bash
uv run python -m src.cli stylize my_clip --style spiderverse
```

Options:

```
--style spiderverse       Style preset to apply (default: spiderverse)
--api-key KEY             Gemini API key (or set GEMINI_API_KEY env var)
--model gemini-2.0-flash-exp   Gemini model (default: gemini-2.0-flash-exp)
```

#### Manual (Gemini in browser or any tool)

1. Open keyframes from `data/keyframes/<name>/`
2. Upload to [Gemini](https://gemini.google.com/) or any image editor
3. Apply the style (use prompts from `config/styles.yaml` as reference)
4. Save styled frames to `data/styled/<name>/<style>/` keeping the same filenames (`frame_00001.png`, etc.)

### 4. Compose the video

```bash
uv run python -m src.cli compose my_clip --style spiderverse
```

Options:

```
--fps 12                  Output video FPS (default: 12)
--with-audio path.mp4     Extract audio from this file and merge into output
--side-by-side            Create a side-by-side comparison video
--original-video path.mp4 Original video for side-by-side (required with --side-by-side)
```

Output goes to `data/output/<name>_<style>.mp4`.

### Other commands

```bash
# List available styles
uv run python -m src.cli styles

# List local clips and their processing status
uv run python -m src.cli clips
```

## Project structure

```
arsenal-style-transfer/
├── src/
│   ├── cli.py                    # Main CLI entry point
│   ├── sourcing/
│   │   ├── scorebat.py           # ScoreBat highlight API client
│   │   └── downloader.py         # yt-dlp video downloader
│   ├── processing/
│   │   ├── frames.py             # Frame extraction (FFmpeg + OpenCV)
│   │   ├── scenes.py             # Scene detection (PySceneDetect)
│   │   └── keyframes.py          # Keyframe selection and export
│   ├── stylize/
│   │   ├── gemini.py             # Gemini API style transfer
│   │   └── presets.py            # Style preset loader
│   └── compose/
│       └── assembler.py          # Video assembly, audio merge, side-by-side
├── config/
│   └── styles.yaml               # Style preset definitions (prompts, FPS, etc.)
├── data/                          # All local data (gitignored)
│   ├── raw/                      # Downloaded video clips
│   ├── frames/                   # Extracted frames (all)
│   ├── keyframes/                # Extracted keyframes (for style transfer)
│   ├── styled/                   # Stylized frames output
│   └── output/                   # Final composed videos
├── models/                        # Model weights if using SD pipeline (gitignored)
├── pyproject.toml
└── README.md
```

## Data flow

```
data/raw/my_clip.mp4
    ↓ process
data/frames/my_clip/frame_00001.png ... frame_00120.png    (all 120 frames)
data/keyframes/my_clip/frame_00001.png ... frame_00109.png (10 keyframes)
    ↓ stylize (gemini API or manual)
data/styled/my_clip/spiderverse/frame_00001.png ... frame_00109.png
    ↓ compose
data/output/my_clip_spiderverse.mp4
```

## Roadmap

- [ ] **EbSynth propagation** — propagate styled keyframes to intermediate frames for smoother output
- [ ] **AnimateDiff + ControlNet** — SD 1.5 pipeline with native temporal consistency
- [ ] **Wan 2.x video-to-video** — highest quality style transfer (cloud GPU)
- [ ] **Canny/depth ControlNet conditions** — preserve player outlines and field depth
- [ ] **Batch processing** — stylize a full match day of highlights in one go
- [ ] **Web UI** — Gradio or Streamlit interface
- [ ] **Audio-aware keyframes** — detect crowd roar peaks for smart keyframe placement
