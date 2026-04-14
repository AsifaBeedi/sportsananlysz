# Feature Implementation Details

This document explains exactly what was implemented in the project, how each feature works, which files are responsible, and what was added or changed to make the system work end to end.

## 1. Project Goal

The goal of this project was to build a **sports CCTV analysis system** with a **sport-agnostic core** and a **tennis demo profile** as the first complete working implementation.

The final system now:

- reads a sports video
- detects players and ball
- tracks motion across frames
- estimates player pose
- computes posture and injury-risk metrics
- detects tennis actions and contact candidates
- estimates racket motion
- estimates ball speed
- estimates an approximate contact-power proxy
- generates explainable recommendations
- writes structured analytics to JSON
- displays analytics, preview frame, and processed output in a dashboard
- saves the full processed annotated video

## 2. Final Architecture

The system is split into:

- **shared sport-agnostic core**
- **sport-specific profile logic**

This means detection, tracking, pose processing, analytics output, and dashboarding are reusable, while interpretation rules can vary by sport.

### Main files

- [data/models/scripts/detects_players.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/data/models/scripts/detects_players.py>)
- [sports_analytics/config.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/config.py>)
- [sports_analytics/pipeline.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/pipeline.py>)
- [sports_analytics/profiles.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/profiles.py>)
- [sports_analytics/pose.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/pose.py>)
- [sports_analytics/posture.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/posture.py>)
- [sports_analytics/events.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/events.py>)
- [sports_analytics/racket.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/racket.py>)
- [sports_analytics/ball_speed.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/ball_speed.py>)
- [sports_analytics/impact_power.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/impact_power.py>)
- [sports_analytics/recommendations.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/recommendations.py>)
- [sports_analytics/session_io.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/session_io.py>)
- [dashboard.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/dashboard.py>)

## 3. End-To-End Pipeline Flow

The runtime flow is:

1. `detects_players.py` parses command-line arguments.
2. `AppConfig` in `config.py` resolves all runtime paths and thresholds.
3. `run_video_session()` in `pipeline.py` opens the video, creates the models, creates the session writer, and starts frame processing.
4. `SportsAnalyticsPipeline.process_frame()` runs the entire analytics chain for each frame.
5. A structured payload is built and written to `match_stats.json`.
6. A preview frame is saved for the dashboard.
7. A full annotated output video is saved to `annotated_match_output.mp4`.
8. `dashboard.py` reads the latest JSON and preview frame and displays the live session.

## 4. What Was Implemented Phase By Phase

### Phase 1: Foundation and Refactor

What was done:

- Created the `sports_analytics` package to separate logic into modules.
- Converted the original script into a proper CLI entry point.
- Centralized runtime settings in `AppConfig`.
- Unified output around one structured JSON payload.
- Added mirrored JSON output for compatibility.
- Replaced dependency on fragile external tracking flow with internal lightweight tracking.

Why this mattered:

- It stopped the project from being a single prototype script.
- It created a reusable analytics backbone for later features.

### Phase 2: Ball Tracking

What was done:

- Added persistent ball trajectory memory across frames.
- Added support for missed-ball recovery using recent history.
- Added trajectory smoothing.
- Added ball history and direction-change candidates to the payload.

How it works:

- The detector extracts `sports ball` candidates from YOLO.
- The tracker keeps the best current ball center.
- If a ball disappears briefly, the track remains active for a few frames.
- Each tracked point is stored in `ball_history`.
- Direction changes are inferred from recent motion vectors.

Why this mattered:

- Later features like contact detection and ball speed depend on a stable ball path.

### Phase 3: Pose Estimation and Joint Angles

What was done:

- Integrated `yolov8n-pose.pt`.
- Extracted named keypoints for each pose detection.
- Matched pose detections to tracked players using box overlap and distance.
- Computed joint angles and trunk lean.

How it works:

- `extract_pose_detections()` converts pose output into named keypoints.
- `match_pose_detections_to_players()` assigns pose boxes to tracked players.
- `build_pose_metrics()` computes:
  - elbow angles
  - knee angles
  - hip angles
  - trunk lean angle

Important implementation detail:

- Trunk lean is measured by comparing the torso vector against a vertical reference vector.

### Phase 4: Posture Analysis and Injury Risk

What was done:

- Added posture scoring.
- Added coaching notes.
- Added injury-risk flags and injury-risk level.

How it works:

- `analyze_posture()` in `posture.py` starts from a base score of `100`.
- The score is reduced using rule-based conditions on:
  - trunk lean
  - knee bend
  - hip posture
  - elbow extension
  - left/right balance gaps

Examples of the rules:

- excessive trunk lean reduces score and adds `excessive_trunk_lean`
- too little knee bend reduces score and adds a coaching note about limited athletic loading
- too much asymmetry between left and right sides reduces score
- near-locked elbow adds an overextension risk flag

Outputs:

- `posture_score`
- `posture_label`
- `injury_risk_level`
- `injury_risk_flags`
- `coaching_notes`

### Phase 5: Tennis Event Detection

What was done:

- Added swing-window logic.
- Added contact-candidate detection.
- Added rough shot labeling.
- Focused event generation on the primary player to reduce noise.

How it works:

- `choose_primary_player()` selects the main player based on size and position.
- `build_player_snapshot()` captures frame-level posture/motion state.
- `compute_activity_score()` combines:
  - wrist movement
  - player center movement
  - elbow-angle change
- `compute_ball_proximity()` measures distance from the ball to relevant player points.
- `is_contact_candidate()` marks likely contact when:
  - ball proximity is small
  - activity is high enough
  - and optionally ball direction change is nearby in time
- `classify_tennis_shot()` labels rough action types such as:
  - `serve_candidate`
  - `forehand_candidate`
  - `backhand_candidate`
  - `volley_candidate`

Outputs:

- `swing_phase`
- `activity_score`
- `ball_proximity_px`
- `shot_label_candidate`
- `contact_candidate`
- event timeline entries in `recent_events`

### Phase 6: Racket Tracking and Swing Path

What was done:

- Implemented a pose-driven racket proxy for tennis.
- Estimated racket handle, tip, angle, swing direction, and path length.

Why a proxy was used:

- There is no custom racket detector in the project.
- Tennis racket tracking was approximated from arm geometry.

How it works:

- `choose_proxy_side()` picks the likely hitting side.
- Wrist, elbow, and shoulder keypoints define a swing vector.
- The vector is extended beyond the wrist to estimate a racket tip.
- Tip positions are saved over time.
- From this history, the code computes:
  - racket angle
  - path length
  - swing direction

Outputs:

- `handle_point`
- `tip_point`
- `angle_deg`
- `path_history`
- `path_length_px`
- `swing_direction`

### Phase 7: Ball Speed Estimation

What was done:

- Implemented tracked ball-speed estimation.
- Added optional real-world speed conversion.
- Added before/after contact speed comparison.

How it works:

- `build_speed_series()` uses consecutive tracked ball points.
- Distance between points is divided by time difference from FPS.
- Output is stored in `px/s`.
- If `meters_per_pixel` is provided, the system also computes:
  - `m/s`
  - `km/h`

Contact comparison:

- `build_contact_comparison()` finds the latest contact candidate.
- It compares the last measured speed before contact with the first measured speed after contact.

Outputs:

- `current_speed`
- `avg_recent_speed_px_per_sec`
- `peak_speed_px_per_sec`
- `speed_series`
- `contact_comparison`

Important limitation:

- Real-world speed is only meaningful if the camera is calibrated and scale is known.

### Phase 8: Recommendation Engine

What was done:

- Added explainable, rule-based coaching feedback.
- Generated session recommendations and player-specific recommendations.

How it works:

- `generate_recommendations()` finds the primary player and secondary players.
- `build_primary_player_recommendations()` checks:
  - posture score
  - coaching notes from posture analysis
  - swing direction
  - shot label
  - ball-speed change around contact
  - ball proximity during active swing
  - racket path length
- `build_secondary_player_recommendations()` flags low-score secondary players.

Important detail:

- The recommendation text is prewritten.
- The system decides whether to show a recommendation using real measured analytics.
- So the feedback is **rule-based and explainable**, not random text generation.

Example triggers:

- low posture score -> lower-body loading recommendation
- limited knee bend -> deeper knee-bend recommendation
- low ball speed gain after contact -> contact-quality recommendation
- ball too far from swing path -> strike-zone/timing recommendation

### Phase 9: Advanced Dashboard

What was done:

- Rebuilt the dashboard into a presentation-friendly UI.
- Added overview, motion, recommendations, history, and raw-data sections.
- Added session freshness and status indicators.
- Added preview frame support.
- Added processed video display.
- Added auto-refresh toggle.

How it works:

- `dashboard.py` reads `match_stats.json`.
- It merges missing fields with a default payload to stay robust.
- It shows:
  - session status
  - source video
  - preview image
  - live metrics
  - charts
  - recommendations
  - processed output video

What was added for stability:

- readable recommendation cards instead of raw dictionaries
- clearer state labels like `Running`, `Completed`, `Stopped`, and `Old Output`
- reset option for clearing previous run output

## 5. Multi-Sport Core

What was done:

- Added sport profiles in `profiles.py` for:
  - tennis
  - cricket
  - baseball
  - hockey

What this means:

- The shared core can be reused across sports.
- Tennis currently has the deepest implemented logic.
- Cricket/baseball/hockey currently benefit from the shared architecture and generic detection/tracking path, but not all tennis-specific event logic applies to them yet.

## 6. Ball Speed and Contact Power

These correspond to the document’s point 5.

### 5.1 Ball Speed Estimation

Implemented in:

- [sports_analytics/ball_speed.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/ball_speed.py>)

What was done:

- ball speed from tracked motion was implemented
- before/after contact comparison was implemented
- calibration-aware real-world conversion was added as an optional mode

When it is reliable:

- fixed camera
- known FPS
- stable tracking
- scale reference or calibration if real-world speed is needed

### 5.2 Power Estimation at Ball-Bat Contact

Implemented as a **proxy** in:

- [sports_analytics/impact_power.py](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/sports_analytics/impact_power.py>)

What was done:

- estimated racket-tip speed around contact
- compared ball speed before and after contact
- combined both into an approximate `power_score`

How it works:

- the latest contact event is found
- the nearest racket-speed segment is found
- ball speed gain around contact is measured
- a bounded power proxy score is computed

Why it is a proxy:

- no true bat/racket force sensor
- no exact mass/force physics modeling
- no perfect 3D contact reconstruction

Important wording:

- This is **not a true physical power measurement**
- It is an **approximate impact-power proxy**

## 7. Dashboard And Output Artifacts

The project now produces:

- main analytics JSON:
  - [match_stats.json](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/match_stats.json>)
- preview frame for dashboard:
  - `latest_annotated_frame.jpg`
- full processed annotated video:
  - [annotated_match_output.mp4](<c:/Users/Asifa Bandulal Beed/Downloads/sports cctv analysis/annotated_match_output.mp4>)

The dashboard can show:

- current processed preview frame
- source video name
- session ID
- runtime and update time
- processed match video

## 8. Stability And Runtime Fixes

Several runtime issues were fixed while building the final demo.

### Null-safety fixes

Problem:

- some players had `pose`, `event_state`, or `racket` set to `None`
- this caused crashes when code tried to read them like dictionaries

Fixes:

- added null-safe reads in:
  - `recommendations.py`
  - `dashboard.py`

### Windows JSON file-lock issue

Problem:

- writing `match_stats.json` sometimes failed with `PermissionError`

Fix:

- `session_io.py` now writes using atomic temp files plus retries

### Preview image lock issue

Problem:

- dashboard access to the preview image could lock the file while the detector tried to replace it

Fix:

- preview writes in `pipeline.py` now use retry logic and cleanup
- preview write failures no longer crash the whole pipeline

### Dashboard websocket/noisy rerun issue

Problem:

- continuous forced reruns created websocket errors in Streamlit

Fix:

- moved to explicit refresh plus controlled auto-refresh
- added clearer session-state indicators

## 9. What Was Added To Make Demo And Sharing Easier

Beyond the core analytics, the following were added to make the project usable:

- `README.md` with run guide
- `PRESENTATION_FLOW.md` for demo explanation
- `IMPLEMENTATION_CHECKLIST.md` tracking all phases
- full processed video export
- preview frame inside dashboard
- session state/freshness indicators
- dashboard reset option

## 10. Current Limitations

The system is complete enough for demo, but some limitations remain:

- Tennis is the strongest and most complete profile.
- Other sports currently reuse the core more than the full event logic.
- Ball and equipment accuracy depends on generic YOLO performance.
- Hockey puck tracking is expected to be weaker.
- Racket logic is proxy-based, not a custom detector.
- Contact power is approximate, not a real physics measurement.
- Real-world speed needs calibration to be meaningful in km/h.

## 11. Summary

The final project is no longer just a prototype detector. It is a structured sports analytics system with:

- reusable architecture
- multi-sport core
- complete tennis demo
- explainable heuristics
- dashboard integration
- saved annotated output video

The most important engineering improvement was turning the original script into a **full pipeline** where each feature builds on the previous one in a clean, testable way.
