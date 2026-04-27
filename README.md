# Sports CCTV Analysis

Sports CCTV Analysis is a multi-sport computer-vision project for recorded video and live capture. It combines a shared analytics pipeline with sport-specific event logic and a Streamlit dashboard for launch, monitoring, and review.

## What Works Today

- session-based analysis outputs under `data/outputs/sessions/<session_id>/`
- source types: `file`, `demo`, `webcam`, `rtsp`
- dashboard launch, stop, live monitor, and session browsing
- baseline analytics across `tennis`, `cricket`, `baseball`, `hockey`, and `volleyball`
- an early `basketball` preview lane for ball-handler, dribble, possession-window, and shot-attempt cues

The strongest current demo is still `tennis`, while `basketball` remains a clearly marked preview path rather than a mature engine.

## Project Layout

- `app/streamlit_app.py`: Streamlit dashboard
- `src/main_pipeline.py`: CLI entry point
- `src/sports_analytics/`: shared analytics core and sport-specific logic
- `src/detection/`, `src/tracking/`, `src/biomechanics/`: cleaned module boundaries for the next racket-sport work
- `data/videos/`: source/demo videos
- `models/`: model weights
- `data/outputs/sessions/`: per-session outputs
- `tools/smoke_test.py`: startup and short-run validation
- `tools/validate_session_payload.py`: payload structure validation
- `SPORT_SUPPORT.md`: truthful current support matrix
- `PERFORMANCE_NOTES.md`: CPU/GPU and demo-readiness notes

## Requirements

- Python 3.10+
- Windows PowerShell or another terminal that can run Python

Install dependencies:

```bash
pip install -r requirements.txt
```

## Quick Start

Run a short smoke test:

```bash
python tools/smoke_test.py --sport tennis --max-frames 1
```

Start the dashboard:

```bash
python -m streamlit run app/streamlit_app.py
```

Open the dashboard and use:

- `Launch` to start uploaded, local, demo, webcam, or RTSP analysis
- `Live` to follow the active session and live job status
- `Dashboard` to inspect saved analytics, events, notes, and artifacts

## CLI Usage

Basic form:

```bash
python src/main_pipeline.py --sport <sport> --source-type <source_type> --no-display
```

Supported sports:

- `tennis`
- `cricket`
- `baseball`
- `hockey`
- `volleyball`
- `basketball`

Supported source types:

- `file`
- `demo`
- `webcam`
- `rtsp`

Examples:

Run the bundled tennis demo:

```bash
python src/main_pipeline.py --sport tennis --source-type demo --no-display --writer-codec mp4v
```

Run a local file:

```bash
python src/main_pipeline.py --sport cricket --source-type file --source data/videos/cricket.mp4 --no-display
```

Run a webcam:

```bash
python src/main_pipeline.py --sport tennis --source-type webcam --source 0 --no-display
```

Run an RTSP stream:

```bash
python src/main_pipeline.py --sport hockey --source-type rtsp --source rtsp://user:pass@camera/stream --no-display
```

Short validation run:

```bash
python src/main_pipeline.py --sport baseball --source-type demo --no-display --no-output-video --writer-codec mp4v --max-frames 5
```

## Output Structure

Each run creates a session folder like:

```text
data/outputs/sessions/tennis-20260422-145530/
```

Each session contains:

- `stats.json`
- `preview.jpg`
- `output.mp4`
- `snippets/`
- `review_frames/`

The latest session still mirrors to the legacy dashboard paths for compatibility:

- `outputs/match_stats.json`

## Validation

Validate the latest saved session payload:

```bash
python tools/validate_session_payload.py --latest --sport tennis
```

Validate every supported sport with a short run:

```bash
python tools/smoke_test.py --all-sports --max-frames 1
```

## Demo Helper

For Windows/PowerShell, use the helper script:

Run a smoke check:

```powershell
.\demo_run.ps1 -Mode smoke -Sport tennis
```

Run a short demo pass and then open the dashboard:

```powershell
.\demo_run.ps1 -Mode demo -Sport cricket -MaxFrames 60
```

Open only the dashboard:

```powershell
.\demo_run.ps1 -Mode dashboard -Port 8501
```

## Current Support Notes

See [SPORT_SUPPORT.md](SPORT_SUPPORT.md) for the truthful sport-by-sport support matrix.

Short version:

- `tennis`: strongest demo lane, best current sport-specific quality
- `cricket`: basic bat and stroke heuristics are active
- `baseball`: basic pitch, swing, and bat-contact heuristics are active
- `hockey`: baseline plus hockey-specific puck/stick heuristics, but most sensitive to tracking quality
- `volleyball`: basic serve, set, spike, block, and dig heuristics are active
- `basketball`: preview-only lane for dribble, pass, drive, rebound, possession-window, and shot-attempt cues

## Performance and Demo Readiness

See [PERFORMANCE_NOTES.md](PERFORMANCE_NOTES.md).

Short version:

- CPU-only is fine for smoke tests and short recordings
- GPU is better for longer sessions and live capture
- demo assets can behave differently across machines because of codec support
- browser playback works best with the default codec order; use `--writer-codec mp4v` and `--no-output-video` only when you want the faster validation path
- live mode is much stronger now, but still deserves a manual browser-level check before a presentation

## Known Limits

- Sport-specific logic is still heuristic-heavy rather than trained on labeled datasets.
- Hockey remains the hardest lane because puck tracking is a small-object problem.
- Basketball is still a preview lane and does not yet have possession-grade team reasoning.
- Detached background jobs are much more observable now, but still should be sanity-checked on the actual demo machine.
- Video-level accuracy across all sports still benefits from manual review in the dashboard.
