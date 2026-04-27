# Sport Support Matrix

This is the truthful support snapshot for the current codebase.

## Shared Platform

All supported sports run through the same shared pipeline for:

- session-local outputs
- player detection and tracking
- pose extraction
- posture metrics
- dashboard session browsing
- upload, demo, webcam, and RTSP ingestion

## Current Support

| Sport | Current Level | Object Tracking | Sport Events | Recommendations | Bundled Validation Clip | Reality Check |
| --- | --- | --- | --- | --- | --- | --- |
| `tennis` | `Full Demo` | YOLO sports-ball tracking | Tennis-specific swing/contact logic | Tennis-specific coaching rules | `data/models/scripts/tennis.mp4` | Strongest demo lane in the repo right now. |
| `badminton` | `Racket Preview` | YOLO sports-ball tracking | Shared racket-sport swing/contact heuristics | Racket-sport preview recommendations + health focus | `data/models/scripts/tennis.mp4` fallback | Uses the racket foundation now; shuttle-specific tracking still needs dedicated validation. |
| `table_tennis` | `Racket Preview` | YOLO sports-ball tracking | Shared racket-sport swing/contact heuristics | Racket-sport preview recommendations + health focus | `data/models/scripts/tennis.mp4` fallback | Uses the racket foundation now; table-specific ball/table logic still needs dedicated validation. |
| `cricket` | `Baseline Core` + `Cricket Basic` | YOLO sports-ball tracking | Basic bat, stroke-window, and contact-candidate heuristics | Cricket-specific first-pass recommendations | `data/models/scripts/cricket.mp4` and `data/models/scripts/sports.mp4` | Useful for early batting reads, not scoring-grade analysis yet. |
| `baseball` | `Baseline Core` + `Baseball Basic` | YOLO sports-ball tracking | Basic pitch-window, swing-window, and bat-contact heuristics | Baseball-specific first-pass recommendations | `data/models/scripts/sports.mp4` | Good for early hitting-pattern demos, still heuristic. |
| `hockey` | `Baseline Core` + `Hockey Basic` | Hockey-specific puck tracker with fallback behavior | Basic stick-motion, possession-candidate, and shot-candidate heuristics | Hockey-specific first-pass recommendations | `data/models/scripts/hockey.mp4` with safe fallback support | Most sensitive to small-object tracking quality and codec issues. |
| `volleyball` | `Baseline Core` + `Volleyball Basic` | YOLO sports-ball tracking | Basic serve, set, spike, block, and dig heuristics | Volleyball-specific first-pass recommendations | `uploaded_videos/volley.mp4` | Good next-step team-sport support, but still an early heuristic lane. |
| `basketball` | `Baseline Limited` + `Basketball Preview` | YOLO sports-ball tracking with basketball-specific motion-recovery fallback | Preview dribble, pass, drive, rebound, possession-window, and shot-attempt cues | Basketball preview recommendations | `uploaded_videos/Screen Recording 2026-04-23 162316.mp4` | Better on the real uploaded clip now, but still not a possession-grade basketball engine yet. |

## Source Types

The platform uses the same source-type names everywhere:

- `file`: an uploaded or local video path
- `demo`: a bundled demo asset selected by sport
- `webcam`: a local camera index or device name
- `rtsp`: an RTSP or IP-camera stream URL

## Output Naming

Each run creates a session folder under `data/sessions/<session_id>/` with:

- `stats.json`
- `preview.jpg`
- `output.mp4`
- `snippets/`
- `review_frames/`

Session IDs now use the standard form:

- `<sport>-YYYYMMDD-HHMMSS`

Example:

- `cricket-20260422-145530`

## Validation Guidance

- Use `tools/smoke_test.py` for a quick startup and short-run sanity check.
- Use `tools/validate_session_payload.py --latest --sport <sport>` to validate the latest saved payload structure.
- Use the dashboard for human review of preview frames, output video, notes, and recommendations.
