# Sports Analytics

Current project update as of 2026-04-29.

## What this project is right now

This is a multi-sport video analysis app built with:

- YOLO object detection
- YOLO pose estimation
- OpenCV video processing
- Streamlit dashboard

The current pipeline can process a video, detect players, estimate pose, track ball-like objects, generate event signals, save annotated output, and show the results in a dashboard.

## Current status

The project is no longer in the early placeholder stage. The core end-to-end flow is working:

1. Load a video or other source
2. Run frame-by-frame analysis
3. Save a session with stats and media outputs
4. Review the session in Streamlit

## What is working

- Player detection and lightweight player tracking
- Pose detection and posture scoring
- Joint-angle based posture analysis
- Ball tracking with fallback logic
- Sport-specific event heuristics
- Racket / bat / stick motion tracking
- Ball-speed and impact-power estimates
- Recommendations generated from detected activity
- Clip saving for important moments
- Bad-frame saving for posture or risk review
- Session-based output folders
- Streamlit dashboard for browsing sessions

## Sport support right now

| Sport | Status | Notes |
|---|---|---|
| Tennis | Strongest profile | Full demo path, stroke classification and racket analytics |
| Badminton | Good preview | Uses shared racket pipeline, useful for posture and contact review |
| Table Tennis | Good preview | Uses shared racket pipeline, useful for compact stroke review |
| Cricket | Baseline core | Basic bat, stroke, and contact-candidate logic active |
| Baseball | Baseline core | Basic pitch-window, swing-window, and contact-candidate logic active |
| Hockey | Baseline core | Dedicated puck detection plus stick-motion and possession-style cues |
| Volleyball | Baseline core | Basic serve, set, spike, block, and dig heuristics active |
| Basketball | Early preview | Exploratory dribble / pass / drive / shot-attempt cues |

## Real output structure

Each run creates a session folder under:

`data/outputs/sessions/<session-id>/`

Typical files:

- `stats.json` - main session analytics payload
- `preview.jpg` - latest annotated preview frame
- `output.mp4` - processed video
- `snippets/` - short clips triggered by important events
- `review_frames/` - saved flagged frames

There is also a latest-style stats file written to:

- `outputs/match_stats.json`
- `match_stats.json`

## Main files

- `streamlit_app.py` - current Streamlit dashboard entry point
- `src/sports_analytics/pipeline.py` - main analysis pipeline
- `src/sports_analytics/profiles.py` - sport support and capability levels
- `src/sports_analytics/run_control.py` - analysis launch helpers

## How to run it

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the dashboard:

```bash
streamlit run streamlit_app.py
```

Run the pipeline directly:

```bash
python -m sports_analytics.pipeline --sport tennis --source-type file --source "path/to/video.mp4" --no-display
```

If needed, make sure `src` is on `PYTHONPATH` when running module commands from outside the project setup.

## Important notes

- `README.md` was previously oversized and stale, and parts of it looked like copied app code instead of documentation.
- `currentstats.md` still describes an older state of the project and is no longer the best source of truth.
- `demo_run.ps1` appears to reference older paths, so it should be treated carefully until updated.

## Best summary of the project today

This project already works as a real sports-analysis prototype with session outputs and a dashboard.

The strongest experience is tennis, while the other sports range from solid shared-pipeline previews to early baseline heuristics. The next big improvement area is tightening sport-specific accuracy and cleaning older helper scripts so the docs and launch scripts all match the current structure.
