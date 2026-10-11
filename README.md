# YouTube Shorts & Longform Automation Pipeline

Autonomous AI video production factory generating high-retention 3D documentary YouTube Shorts ([@zackdfilms](https://www.youtube.com/@zackdfilms) style) and 16:9 investigative longform documentaries.

---

## 🌟 Overview & Capabilities

- **Zack D. Films 3D Shorts (9:16 vertical, 1080x1920)**:
  - Glossy stylized 3D mannequin aesthetic (subsurface scattering SSS, mineralized cortical bone, non-Newtonian fluids).
  - Continuous camera flight across 6 scale transitions (`wide <-> medium <-> close <-> macro <-> micro <-> nano`).
  - Strict non-speaking characters (closed/neutral mouth, no dialogue).
  - Word-timed animated subtitles rendered via FFmpeg/ASS in lower-middle caption-safe zones.
  - Tri-modality detection (`incident > mechanical > anatomical`) with customized visual and audio profiles.
  - Broadcast-standard audio mastering (-14 LUFS, -1.5 dBTP) with ASMR Foley hit envelopes and mood-matched synth beds.

- **Investigative Longform Documentaries (16:9 widescreen, 1920x1080)**:
  - Persistent host persona: 28-year-old chronological time-traveler & explorer **Nova** (`services/character.py`).
  - Model A Hybrid Compilation: 10–15% generative AI Video moments for key narrative turning points via Google Flow + 85–90% 2.5D Ken Burns Pan/Zoom montages for archaeological/historical B-Roll.
  - Zero-focus background generation via Playwright CDP (port 9223) without interrupting OS focus or mouse input.

---

## 🏗️ Architecture

```
YOUTUBE/
├── main.py              # CLI entry point (--topic, --auto-topic, --dry-run, --format)
├── pipeline.py          # Orchestration pipeline across generation stages
├── editor.py            # FFmpeg filtergraph compiler & broadcast audio mastering
├── config.py            # System configuration, thresholds, and environment loader
├── narrative.py         # LLM screenplay generation & prompt compiler
├── metadata.py          # YouTube upload metadata & SEO generator
├── release.py           # Packaging & QA inspection
├── core/                # Core domain abstractions
├── providers/           # Swappable multi-provider adapters (LLM, Image, Video, Voice, SFX)
│   ├── llm/             # Vertex Gemini, Gemini Flash
│   ├── image/           # Nano Banana Pro, Flow Agent, Playwright Flow
│   ├── video/           # Vertex Veo, Fal.ai, Flow Agent, Playwright Flow
│   ├── voice/           # Deepgram Aura-2, ElevenLabs, Edge TTS
│   └── sfx/             # Local Manifest, MMAudio, ElevenLabs
├── services/            # Domain services (Screenplay, Foley, Audio Bed, Character, Research)
├── scripts/             # Utility scripts, audits, and CLI tools
├── assets/              # Sound effects, stock music, and prompt templates
└── tests/               # Pytest suite verifying timeline contracts, FFmpeg safety, and adapters
```

---

## 🛠️ Quick Start

### 1. Prerequisites
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) (compiled with `--enable-libass`) added to your system `PATH`
- Google Cloud Vertex AI credentials, Deepgram API key, and/or Fal.ai keys depending on your chosen providers

### 2. Installation
```bash
git clone https://github.com/hyper-maker-app/youtube.git
cd youtube
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and fill in your API credentials:
```bash
cp .env.example .env
```

### 4. Running the Pipeline

**Local Dry Run (No API calls, FFmpeg synthesis only):**
```bash
python main.py --dry-run --topic "Why You Can't Open an Airplane Door Mid-Flight"
```

**Production Short (9:16 vertical):**
```bash
python main.py --topic "Why You Can't Open an Airplane Door Mid-Flight" --video vertex_veo --image nano_banana_pro
```

**16:9 Longform Mode:**
```bash
python main.py --format longform --topic "The Lost Labyrinth of Hawara" --video playwright_flow --image playwright_flow
```

---

## 🛡️ Architecture Decision Records (ADR) & Memory

All architectural decisions, benchmarks, and abandoned experiments are recorded in [`DECISIONS.md`](DECISIONS.md). The pipeline integrates local MCP servers:
- `youtube-decision-memory`: ADR search and logging.
- `youtube-research`: Automated claim evaluation.
- `youtube-media-inspector`: LUFS audio measurement and black frame detection.
- `youtube-pipeline-db`: Production run history.

Run the self-audit anytime:
```bash
python scripts/audit_and_sync.py
```

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
