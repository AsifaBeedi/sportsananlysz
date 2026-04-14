# Sports Analytics Implementation Checklist

This project uses a sport-agnostic core with tennis as the first demo sport.
The shared core will handle video input, detection, tracking, pose, analytics, event generation, structured outputs, and dashboard integration.
Tennis-specific logic will be layered on top for shot interpretation, racket events, and coaching rules.

## Phase 1: Foundation and Refactor

- [x] Audit the current prototype and identify reusable pieces.
- [x] Create a clean module boundary for config, pipeline logic, and JSON output.
- [x] Standardize runtime paths for model, video, and analytics output files.
- [x] Unify the session output format so the detector and dashboard read the same structure.
- [x] Refactor the detector script into a proper entry point with runtime options.
- [x] Upgrade the dashboard to read structured analytics instead of a single raw count.
- [x] Add a sport-profile layer for tennis, cricket, baseball, and hockey.
- [x] Add a small README or run guide if needed after the pipeline stabilizes.

Phase 1 deliverable:
A clean, runnable baseline that still performs player and ball detection, writes structured analytics, and feeds the dashboard from a single source of truth.

## Phase 2: Robust Ball Tracking

- [x] Add persistent ball trajectory memory across frames.
- [x] Smooth noisy ball motion and handle brief missed detections.
- [x] Store ball path history in structured JSON output.
- [x] Surface trajectory overlays and direction-change candidates.

Phase 2 deliverable:
Stable ball path tracking suitable for event detection and speed estimation.

## Phase 3: Pose Estimation and Joint Angles

- [x] Integrate the pose model already present in the project.
- [x] Associate pose keypoints with tracked player IDs.
- [x] Compute key joint angles for tennis posture analysis.
- [x] Add pose data to the session output and overlays.

Phase 3 deliverable:
Per-player pose and biomechanics-ready angle data.

## Phase 4: Posture Analysis and Injury Risk

- [x] Define tennis posture heuristics for stance, balance, bend, and follow-through.
- [x] Compute posture quality scores from joint-angle patterns.
- [x] Add injury-risk heuristics for overextension, awkward lean, and poor loading.
- [x] Expose posture and alert summaries in the dashboard.

Phase 4 deliverable:
Actionable posture metrics and injury-risk indicators.

## Phase 5: Tennis Event Detection

- [x] Detect swing windows from temporal movement and pose changes.
- [x] Detect likely contact events from ball proximity and ball path changes.
- [x] Segment actions into preparation, contact, and follow-through windows.
- [x] Add coarse shot labels such as forehand, backhand, serve, and volley.

Phase 5 deliverable:
An event timeline with meaningful tennis action labels.

## Phase 6: Racket Tracking and Swing Path

- [x] Add racket localization or a reliable racket-motion proxy.
- [x] Estimate swing arc and racket movement direction.
- [x] Track racket-side motion relative to the player pose.
- [x] Visualize swing path in both overlay and structured outputs.

Phase 6 deliverable:
Tennis-specific replacement for the bat path and bat tracking requirement.

## Phase 7: Ball Speed Estimation

- [x] Compute ball speed in pixel units from tracked trajectory.
- [x] Add calibrated real-world speed when camera scale assumptions are available.
- [x] Compare pre-contact and post-contact speed where possible.
- [x] Expose speed metrics and trends in the dashboard.

Phase 7 deliverable:
Ball speed analytics that are demo-ready and calibration-aware.

## Phase 8: Recommendation Engine

- [x] Map posture and event metrics to coaching recommendations.
- [x] Generate event-level and session-level feedback.
- [x] Add explainable reasons behind each recommendation.

Phase 8 deliverable:
Human-readable improvement suggestions based on measurable signals.

## Phase 9: Advanced Dashboard

- [x] Show live player, ball, posture, and event metrics.
- [x] Add charts for speed, alerts, and session progress.
- [x] Show a session summary and recommendation panel.
- [x] Prepare the UI for future historical session comparison.

Phase 9 deliverable:
A polished analytics dashboard that reflects the full pipeline.

## Cross-Cutting Rules

- Keep the core logic sport-agnostic wherever possible.
- Keep tennis-specific heuristics isolated so future sports can be plugged in later.
- Prefer structured outputs over ad-hoc variables to keep the dashboard and analytics aligned.
- Start with explainable rule-based logic before training custom ML classifiers.
