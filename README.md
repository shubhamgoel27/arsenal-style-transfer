# Arsenal Style Transfer

Convert Arsenal FC match highlights into different animation styles — Spiderverse ink-splatter, Pokemon anime, Studio Ghibli, comic book, and more.

## How it works

```
[Source Clips] → [Extract Frames] → [Style Transfer] → [Compose Video]
     │                 │                   │                   │
  ScoreBat API     FFmpeg @ 12fps     Gemini API          FFmpeg
  YouTube search   Scene detection    or manual upload     + audio merge
  Local files      Keyframe selection                      + side-by-side
```

1. **Source** — Find Arsenal highlights via ScoreBat, search YouTube, or use local files
2. **Process** — Extract frames at a target FPS and select keyframes for style transfer
3. **Stylize** — Run keyframes through Gemini API or manually upload to any image tool
4. **Compose** — Stitch styled frames back into a video with optional audio and comparison

## Setup

### Prerequisites

- **Python 3.11+**
- **[FFmpeg](https://ffmpeg.org/)** — installed and on PATH (`brew install ffmpeg` on macOS)
- **[uv](https://docs.astral.sh/uv/)** — Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Install

```bash
git clone https://github.com/shubhamgoel27/arsenal-style-transfer.git
cd arsenal-style-transfer
uv sync
```

### Gemini API key (optional)

Required only for automated style transfer via the `stylize` command. Manual workflow doesn't need this.

1. Get a free key from https://aistudio.google.com/apikey
2. Set it:
   ```bash
   export GEMINI_API_KEY=your_key_here
   ```

Free tier gives ~15 requests/minute — plenty for keyframe-based stylization.

---

## Quick start

```bash
# 1. Browse recent Arsenal highlights
uv run python -m src.cli highlights

# 2. Download one (e.g. index 4 = Arsenal vs Chelsea)
uv run python -m src.cli highlights -d 4

# 3. Extract frames and keyframes
uv run python -m src.cli process data/raw/2026/PL/Arsenal_-_Chelsea/clip.mp4

# 4a. Auto-stylize keyframes via Gemini API
uv run python -m src.cli stylize clip_name --style spiderverse

# 4b. OR manually: upload keyframes from data/keyframes/<name>/ to Gemini,
#     save styled images to data/styled/<name>/spiderverse/ with same filenames

# 5. Compose into video
uv run python -m src.cli compose clip_name --style spiderverse
```

---

## Commands

All commands are run from the project root. Use `--help` on any command for full details.

### `highlights` — Browse and download Arsenal highlights

Fetches recent Arsenal match highlights from ScoreBat and displays them in a table.
Use `-d` to download a specific one via YouTube search.

```bash
uv run python -m src.cli highlights [OPTIONS]
```

| Option | Short | Default | Description |
|---|---|---|---|
| `--limit` | `-n` | `10` | Number of highlights to fetch |
| `--download` | `-d` | — | Download the highlight at this index |

```bash
# Browse recent highlights
uv run python -m src.cli highlights

# Download highlight #0 (first in the list)
uv run python -m src.cli highlights -d 0

# Show only the last 5
uv run python -m src.cli highlights -n 5
```

Downloaded clips are saved to `data/raw/<year>/<competition>/<match>/`.

### `download` — Download any video by URL or search

Accepts a direct YouTube URL or a free-text search query. When searching, results are
**ranked by authenticity** — FIFA/EA FC gameplay, prediction videos, and simulations are
automatically filtered out. Trusted channels (Arsenal, NBC Sports, Sky Sports, etc.) are
prioritized.

```bash
uv run python -m src.cli download [OPTIONS] QUERY
```

| Option | Short | Default | Description |
|---|---|---|---|
| `QUERY` (argument) | — | *required* | YouTube URL or search terms |
| `--output-dir` | `-o` | `data/raw` | Base directory to save the clip |
| `--max-duration` | — | `600` | Skip results longer than this (seconds) |
| `--max-height` | — | `720` | Max video resolution height in pixels |

```bash
# Direct YouTube URL
uv run python -m src.cli download "https://www.youtube.com/watch?v=abc123"

# Free-text search
uv run python -m src.cli download "Arsenal Saka goal 2026"

# Only short clips (under 2 min)
uv run python -m src.cli download "Arsenal goals" --max-duration 120

# Download in 1080p
uv run python -m src.cli download "Arsenal highlights" --max-height 1080
```

**How filtering works:**

Each YouTube result is scored on:
- **Trusted channel** (+500): Arsenal, Sky Sports, NBC Sports, Premier League, BBC Sport, etc.
- **Highlight keywords** (+50 each): "highlight", "goal", "save", "assist", "extended"
- **View count** (+10 to +80): popular videos are more likely real
- **Duration** (+100): 30s-600s is the sweet spot for highlights
- **Blacklisted** (-1000): anything with "FIFA", "simulation", "EA FC", "prediction", "PS5", etc.

### `process` — Extract frames and keyframes

Extracts video frames at a target FPS using FFmpeg, then selects keyframes at a regular
interval. Keyframes are the subset sent to style transfer.

```bash
uv run python -m src.cli process [OPTIONS] VIDEO
```

| Option | Short | Default | Description |
|---|---|---|---|
| `VIDEO` (argument) | — | *required* | Path to a video file (.mp4) |
| `--fps` | `-f` | `12` | Frames per second to extract |
| `--keyframe-interval` | `-k` | `12` | Select every Nth frame as a keyframe |
| `--name` | `-n` | filename | Custom name for this clip |

```bash
# Default: 12 FPS, keyframe every 12 frames (= 1 keyframe per second)
uv run python -m src.cli process data/raw/2026/PL/Arsenal_-_Chelsea/clip.mp4

# Smoother output: 24 FPS
uv run python -m src.cli process clip.mp4 -f 24

# More keyframes for style transfer (1 every 6 frames = 2 per second)
uv run python -m src.cli process clip.mp4 -k 6

# Custom name to keep it short
uv run python -m src.cli process data/raw/.../long_clip_name.mp4 -n arsenal_chelsea
```

**Understanding FPS and keyframe interval:**

| Setting | 2 min clip | Frames | Keyframes | Style transfer time (Gemini free tier) |
|---|---|---|---|---|
| `-f 12 -k 12` (default) | 120s | 1440 | 120 | ~9 min |
| `-f 12 -k 6` | 120s | 1440 | 240 | ~18 min |
| `-f 24 -k 24` | 120s | 2880 | 120 | ~9 min |
| `-f 8 -k 8` | 120s | 960 | 120 | ~9 min |

Output:
- `data/frames/<name>/` — all extracted frames
- `data/keyframes/<name>/` — keyframes only (for style transfer or manual upload)

### `stylize` — Apply animation style via Gemini API

Sends each keyframe to Gemini with a style prompt and saves the generated image.
Requires `GEMINI_API_KEY` environment variable or `--api-key` flag.

```bash
uv run python -m src.cli stylize [OPTIONS] CLIP_NAME
```

| Option | Short | Default | Description |
|---|---|---|---|
| `CLIP_NAME` (argument) | — | *required* | Name of a processed clip |
| `--style` | `-s` | `spiderverse` | Style preset (see `styles` command) |
| `--api-key` | — | `$GEMINI_API_KEY` | Gemini API key |
| `--all-frames` | — | `false` | Stylize ALL frames, not just keyframes |
| `--model` | `-m` | `gemini-2.0-flash-exp` | Gemini model ID |
| `--delay` | — | `4.5` | Seconds between API requests |

```bash
# Spiderverse style (default)
uv run python -m src.cli stylize my_clip

# Ghibli style
uv run python -m src.cli stylize my_clip -s ghibli

# All frames (slower but smoother result)
uv run python -m src.cli stylize my_clip -s pokemon --all-frames

# Faster with paid tier (lower delay between requests)
uv run python -m src.cli stylize my_clip -s comic_book --delay 1.0
```

Output: `data/styled/<clip_name>/<style>/`

**Manual style transfer (no API key needed):**

Skip the `stylize` command entirely. Instead:

1. Open keyframes from `data/keyframes/<name>/`
2. Upload to [Gemini](https://gemini.google.com/), ChatGPT, or any image editor
3. Apply the style (use prompts from `config/styles.yaml` as reference)
4. Save styled images to `data/styled/<name>/<style>/` keeping the same filenames (`frame_00001.png`, `frame_00013.png`, etc.)
5. Run `compose` as usual

### `compose` — Assemble styled frames into video

Stitches styled PNG frames back into an mp4 video. Optionally merges audio from the
original clip and creates a side-by-side comparison.

```bash
uv run python -m src.cli compose [OPTIONS] CLIP_NAME
```

| Option | Short | Default | Description |
|---|---|---|---|
| `CLIP_NAME` (argument) | — | *required* | Name of the processed clip |
| `--style` | `-s` | `spiderverse` | Style that was applied |
| `--fps` | `-f` | `12` | Output video FPS |
| `--audio` | `-a` | — | Path to original video to extract audio from |
| `--side-by-side` | — | `false` | Create a side-by-side comparison |
| `--original` | — | — | Original video path (required for `--side-by-side`) |

```bash
# Basic: frames to video
uv run python -m src.cli compose my_clip -s spiderverse

# With original audio merged in
uv run python -m src.cli compose my_clip -s ghibli -a data/raw/.../original.mp4

# Side-by-side comparison (original | styled)
uv run python -m src.cli compose my_clip -s pokemon \
  --side-by-side --original data/raw/.../original.mp4
```

Output: `data/output/<clip_name>_<style>.mp4`

### `styles` — List available style presets

```bash
uv run python -m src.cli styles
```

Shows all styles defined in `config/styles.yaml` with their full prompts.

### `clips` — List downloaded clips

```bash
uv run python -m src.cli clips
```

Shows all downloaded clips with their size and whether frames have been extracted.

---

## Available styles

| Style | Description |
|---|---|
| `spiderverse` | Spider-Verse ink splatter, halftone dots, Ben-Day dots, bold outlines |
| `pokemon` | Flat cel-shaded anime, bold black outlines, bright saturated palette |
| `ghibli` | Soft watercolor textures, warm lighting, painterly backgrounds |
| `comic_book` | Thick ink outlines, dramatic shadows, action lines |
| `pixel_art` | 16-bit retro game aesthetic, limited color palette |
| `ukiyo_e` | Japanese woodblock print, flat color areas, flowing outlines |

### Adding custom styles

Edit `config/styles.yaml`:

```yaml
styles:
  my_style:
    prompt: "Redraw this image in [your style description]. Keep the exact same composition, player positions, and action."
    fps: 12
    keyframe_interval: 12
```

---

## Directory structure

```
arsenal-style-transfer/
├── src/
│   ├── cli.py                    # CLI entry point (7 commands)
│   ├── sourcing/
│   │   ├── scorebat.py           # ScoreBat API client (match discovery)
│   │   └── downloader.py         # YouTube search + download with fake filtering
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
│   └── styles.yaml               # Style definitions (prompts + settings)
├── data/                          # All local data (gitignored)
│   ├── raw/                      # Downloaded clips: year/competition/match/
│   ├── frames/                   # All extracted frames
│   ├── keyframes/                # Keyframes only (for style transfer)
│   ├── styled/                   # Stylized frames
│   └── output/                   # Final composed videos
└── pyproject.toml
```

### Data directory layout

Downloads are organized by year, competition, and match:

```
data/raw/
├── 2026/
│   ├── PL/
│   │   ├── Arsenal_-_Chelsea/
│   │   │   └── SALIBA_TIMBER_GOALS_....mp4
│   │   └── Brighton_-_Arsenal/
│   │       └── SAKA_SECURES_THREE_....mp4
│   ├── FA_Cup/
│   │   └── Mansfield_Town_-_Arsenal/
│   │       └── THE_GUNNERS_REACH_....mp4
│   └── UCL/
│       └── ...
```

Competition abbreviations: `PL` (Premier League), `FA_Cup`, `UCL` (Champions League), `UEL` (Europa League), `Carabao_Cup`, `Community_Shield`.

---

## Full walkthrough

### End-to-end: Arsenal vs Chelsea in Spiderverse style

```bash
# Step 1: Download
uv run python -m src.cli download "Arsenal vs Chelsea highlights Premier League 2026"
# → data/raw/2026/PL/Arsenal_-_Chelsea/SALIBA_TIMBER_GOALS_....mp4

# Step 2: Extract frames
uv run python -m src.cli process data/raw/2026/PL/Arsenal_-_Chelsea/SALIBA_TIMBER_GOALS_EARN_ALL_THREE_POINTS_HIGHLIGHTS_Arsenal_vs_Chelsea_2-1_l_Pr.mp4 -n arsenal_chelsea
# → data/frames/arsenal_chelsea/    (1440 frames)
# → data/keyframes/arsenal_chelsea/ (120 keyframes)

# Step 3: Stylize
export GEMINI_API_KEY=your_key
uv run python -m src.cli stylize arsenal_chelsea -s spiderverse
# → data/styled/arsenal_chelsea/spiderverse/ (120 styled frames)

# Step 4: Compose video
uv run python -m src.cli compose arsenal_chelsea -s spiderverse
# → data/output/arsenal_chelsea_spiderverse.mp4

# Optional: with audio and side-by-side
uv run python -m src.cli compose arsenal_chelsea -s spiderverse \
  -a data/raw/2026/PL/Arsenal_-_Chelsea/SALIBA_TIMBER_GOALS_....mp4 \
  --side-by-side --original data/raw/2026/PL/Arsenal_-_Chelsea/SALIBA_TIMBER_GOALS_....mp4
```

### Manual workflow with Gemini in the browser

```bash
# Steps 1-2: same as above
uv run python -m src.cli download "Arsenal Saka goal"
uv run python -m src.cli process data/raw/.../clip.mp4 -n saka_goal

# Step 3: Open data/keyframes/saka_goal/ in Finder
# Upload each keyframe to gemini.google.com
# Prompt: "Redraw this in Spiderverse style with ink splatter and halftone dots"
# Save each result to data/styled/saka_goal/spiderverse/ with the same filename

# Step 4: Compose
uv run python -m src.cli compose saka_goal -s spiderverse
```

---

## How the YouTube search filtering works

When you search via `highlights -d` or `download`, the tool fetches 15 YouTube results
and scores each one to pick the most authentic highlight video:

| Signal | Score | Example |
|---|---|---|
| Trusted channel (Arsenal, NBC Sports, Sky Sports, etc.) | +500 | "Arsenal" official channel |
| Highlight keywords in title | +50 each | "HIGHLIGHTS", "goal", "save" |
| Competition name in title | +30 | "Premier League", "FA Cup" |
| Duration 30s-600s | +100 | 2-minute highlight reel |
| View count > 100k | +80 | Popular = likely real |
| **Blacklisted** (FIFA, simulation, gameplay, etc.) | **-1000** | "EA FC 26 - Arsenal vs Chelsea" |

Videos with negative scores are rejected. The highest-scoring video is downloaded.

**Blacklisted terms:** FIFA, EA FC, eFootball, PES, Football Manager, simulation, prediction, gameplay, PS4, PS5, Xbox, career mode, and more.

**Trusted channels:** Arsenal, Premier League, NBC Sports, Sky Sports, BT Sport, TNT Sports, BBC Sport, CBS Sports Golazo, ESPN, DAZN, beIN Sports, Optus Sport, Match of the Day.

---

## Roadmap

- [ ] EbSynth frame propagation — stylize keyframes, propagate to intermediate frames via optical flow
- [ ] AnimateDiff + ControlNet — native temporal consistency for smoother animation
- [ ] Wan 2.x video-to-video — highest quality style transfer on cloud GPU
- [ ] Canny edge + depth map extraction — better structural preservation during style transfer
- [ ] Batch processing — stylize a full match day of highlights in one run
- [ ] Web UI (Gradio/Streamlit) — browser interface for non-CLI users
- [ ] Smart keyframe density — more keyframes during fast action, fewer during replays
