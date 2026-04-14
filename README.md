# Sports CCTV Analysis

A sport-agnostic computer vision pipeline for player tracking, ball tracking, pose estimation, posture analysis, event detection, equipment motion analysis, coaching recommendations, and dashboard-based monitoring.

The current demo profile is **tennis**, but the core has been structured so other sports can plug into the same pipeline. Supported sport profiles in the current codebase are:

- `tennis`
- `cricket`
- `baseball`
- `hockey`

## Project Status

All planned build phases in the implementation checklist are complete:

- Phase 1: Foundation and refactor
- Phase 2: Ball tracking
- Phase 3: Pose estimation and joint angles
- Phase 4: Posture analysis and injury risk
- Phase 5: Tennis event detection
- Phase 6: Racket tracking and swing path
- Phase 7: Ball speed estimation
- Phase 8: Recommendation engine
- Phase 9: Advanced dashboard

## What The System Does

The pipeline can currently:

- detect and track players
- detect and track the ball with short-term recovery and smoothing
- run pose estimation on tracked players
- compute joint-angle and posture metrics
- generate posture and injury-risk signals
- detect tennis-style swing/contact events
- estimate racket-side motion using a racket proxy
- estimate ball speed from trajectory
- produce rule-based coaching recommendations
- write structured analytics JSON for the dashboard

## Architecture

Core package: [sports_analytics](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics)

Main modules:

- [config.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/config.py)
- [pipeline.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/pipeline.py)
- [profiles.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/profiles.py)
- [pose.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/pose.py)
- [posture.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/posture.py)
- [events.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/events.py)
- [racket.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/racket.py)
- [ball_speed.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/ball_speed.py)
- [recommendations.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/recommendations.py)
- [session_io.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/session_io.py)

Entry points:

- Detector CLI: [detects_players.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/data/models/scripts/detects_players.py)
- Dashboard: [dashboard.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/dashboard.py)

## Folder Notes

- `data/models/scripts/` contains the demo videos and YOLO model files.
- `match_stats.json` is the main structured analytics output used by the dashboard.
- `data/models/scripts/match_stats.json` is a mirrored legacy path kept in sync for compatibility.
- `IMPLEMENTATION_CHECKLIST.md` tracks the project roadmap and completion state.

## Requirements

Recommended environment:

- Python 3.10+
- Windows PowerShell or any terminal that can run Python

Expected Python packages:

```bash
pip install ultralytics opencv-python streamlit numpy
```

If your local setup already has these packages, you do not need to reinstall them.

## How To Run

Open two terminals in the project root.

Terminal 1: run the analytics pipeline

```bash
python data/models/scripts/detects_players.py --sport tennis --video data/models/scripts/tennis.mp4
```

Terminal 2: run the dashboard

```bash
streamlit run dashboard.py
```

The detector writes live session output to `match_stats.json`, and the dashboard refreshes from that file.

## Useful CLI Examples

Run tennis in headless mode:

```bash
python data/models/scripts/detects_players.py --sport tennis --video data/models/scripts/tennis.mp4 --no-display
```

Quick validation run:

```bash
python data/models/scripts/detects_players.py --sport tennis --video data/models/scripts/tennis.mp4 --no-display --max-frames 20
```

Switch sport profile while keeping the same shared core:

```bash
python data/models/scripts/detects_players.py --sport cricket --video data/models/scripts/football.mp4 --no-display
python data/models/scripts/detects_players.py --sport baseball --video data/models/scripts/sports.mp4 --no-display
python data/models/scripts/detects_players.py --sport hockey --video data/models/scripts/hockey.mp4 --no-display
```

Optional calibration for real-world ball-speed conversion:

```bash
python data/models/scripts/detects_players.py --sport tennis --video data/models/scripts/tennis.mp4 --ball-meters-per-pixel 0.01
```

## Dashboard Highlights

The dashboard now includes:

- sidebar session status and sport profile
- top-level live metrics
- overview tab for session summary and tracked players
- motion tab for speed and progress charts
- recommendations tab for coaching output and risk summaries
- history tab for lightweight in-app session history
- raw data tab for inspection and debugging

## Sport-Agnostic Design

The project is intentionally split into two layers:

- shared analytics core
- sport-specific profile logic

That means detection, tracking, pose handling, structured output, and dashboarding are reusable, while sport interpretation can change by profile. Tennis is the current demo, but the system structure is ready for future cricket, baseball, and hockey logic expansions.

## Current Limitations

- Tennis is the strongest demo profile today.
- Generic YOLO detection does not guarantee equally strong equipment or ball performance across every sport.
- Hockey puck tracking is expected to be weaker than larger ball-based sports.
- Racket tracking is currently a pose-driven proxy, not a custom trained racket detector.
- Many sport-specific event rules are still heuristic rather than learned from labeled data.

## Suggested Demo Flow

Use the companion guide here:

- [PRESENTATION_FLOW.md](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/PRESENTATION_FLOW.md)

## Next Improvements

- add a `requirements.txt`
- save completed sessions for historical comparison across runs
- train sport-specific ball and equipment detectors
- strengthen cricket, baseball, and hockey event logic
- calibrate real-world speed using court or field geometry
