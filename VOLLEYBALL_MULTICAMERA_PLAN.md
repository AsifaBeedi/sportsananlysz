# Volleyball And Multi-Camera Expansion Plan

This document is the concrete implementation plan for the next expansion phase of the sports analytics platform.

The goal is not just to add another sport quickly, but to add it in a way that keeps the shared platform clean and also creates the foundation for multi-camera workflows.

## 1. Why Volleyball First

Volleyball is the better next sport before basketball for this codebase.

Reasons:

- It matches the current strengths of the platform: pose, jumps, ball trajectory, event windows, and explainable heuristics.
- It does not require possession logic as early as basketball does.
- It gives us a cleaner path to serves, sets, spikes, digs, and blocks using the same player-plus-ball-plus-pose pipeline.
- It improves team-sport support without forcing a full identity-and-possession architecture immediately.

Basketball should still be added after this phase, but volleyball is the better next step.

## 2. Phase Goals

We want to deliver three things in this phase:

1. Volleyball support as a first-class sport in the current platform.
2. Level-1 multi-camera support using parallel sessions under one match group.
3. A quality sprint to improve event visibility, recommendations, and trend metrics.

## 3. Delivery Principles

- Keep the shared pipeline shared.
- Do not hard-code volleyball logic into generic modules when a profile-specific path is enough.
- Add multi-camera support first as linked sessions, not fused computer vision.
- Prefer a clean match-session abstraction over hacking multiple cameras into one session folder.
- Every milestone should be demoable with recorded files before live camera workflows.

## 4. Milestone 7: Volleyball Support

Goal:
Add volleyball as the next explicit sport engine on top of the shared platform.

### Scope

- Add `volleyball` to supported sport profiles.
- Add a volleyball baseline mode.
- Add volleyball event heuristics.
- Add volleyball recommendations.
- Add volleyball support labels and dashboard wording.
- Add at least one validation clip path and smoke-test coverage.

### Suggested event set for v1

- `serve_window`
- `set_window`
- `spike_window`
- `block_window`
- `dig_candidate`
- `jump_attack_candidate`
- `ball_contact_candidate`

### Suggested heuristics for v1

- Detect jump-like body motion from pose and vertical center changes.
- Use wrist and shoulder motion to separate set-like vs spike-like action.
- Use ball height relative to shoulder/head line to distinguish overhead actions.
- Use player-ball proximity plus short activity bursts for contact candidates.
- Use two-player overhead convergence near the net region for block candidates.

### Files to change first

- [sports_analytics/profiles.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/profiles.py)
- [sports_analytics/events.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/events.py)
- [sports_analytics/recommendations.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/recommendations.py)
- [sports_analytics/racket.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/racket.py)
- [dashboard.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/dashboard.py)
- [SPORT_SUPPORT.md](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/SPORT_SUPPORT.md)
- [README.md](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/README.md)

### Definition of done

- `volleyball` appears in the dashboard sport selector.
- A volleyball session runs end to end through the shared pipeline.
- The payload clearly identifies volleyball mode.
- The dashboard shows volleyball-specific capability messaging.
- At least one event window and one recommendation path can be demonstrated on a real clip.

## 5. Milestone 8: Multi-Camera Level 1

Goal:
Support multiple camera feeds as linked sessions under one match group.

This is not full camera fusion yet. Each camera still runs its own analysis pipeline, but the dashboard can group and compare them.

### What Level 1 means

- Multiple camera sessions can belong to one `match_id`.
- Each camera keeps its own `session_id`.
- The dashboard can browse grouped sessions by match.
- Users can compare camera outputs side by side.
- Event timelines can be reviewed together at the dashboard level.

### What Level 1 does not mean

- No cross-camera re-identification yet.
- No homography or court calibration fusion yet.
- No single fused player track across cameras yet.

### New concepts to add

- `match_id`
- `camera_id`
- `camera_label`
- `camera_role`

Examples:

- `camera_id=cam_a`
- `camera_role=side`
- `camera_role=endline`
- `camera_role=wide`

### Suggested session model

Current:

- `data/sessions/<session_id>/`

Next:

- `data/matches/<match_id>/<camera_id>/<session_id>/`

Compatibility path:

- Keep `data/sessions/<session_id>/` working during transition.
- Mirror grouped session metadata into session payloads so the dashboard can group without rewriting everything at once.

### Files to change first

- [sports_analytics/config.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/config.py)
- [sports_analytics/session_io.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/session_io.py)
- [sports_analytics/pipeline.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/pipeline.py)
- [sports_analytics/run_control.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/run_control.py)
- [sports_analytics/dashboard_utils.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/dashboard_utils.py)
- [dashboard.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/dashboard.py)

### UI changes for Level 1

- Add `match setup` to the launch page.
- Allow user to assign `match_id` and `camera_label`.
- Add `Multi-Camera` page or tab to browse grouped sessions.
- Show two or more preview frames side by side.
- Show grouped event timeline table.
- Allow selecting one camera as the primary view.

### Definition of done

- Two recorded files can be launched under the same match group.
- The dashboard can open the match and show both camera sessions.
- Users can compare preview frames and recent events across cameras.

## 6. Milestone 9: Inference Quality Sprint

Goal:
Improve the usefulness of what users actually see: event confidence, charts, recommendations, and interpreted output quality.

### Focus areas

- Better event thresholds and fewer empty result screens.
- More robust capture-quality recommendations.
- Better motion and path metrics for bat, racket, and stick.
- Stronger trend charts and labels in the dashboard.
- Better clip-trigger coverage for important moments.

### Concrete tasks

- Add session-level confidence or evidence fields to event payloads.
- Add stronger shot-label persistence across neighboring frames.
- Add per-session dominant action summary.
- Add clearer graph titles and sport-specific metric names.
- Improve recommendation fallback behavior when no contact is confirmed.
- Add more session-level summary cards in the dashboard.

### Files most likely to change

- [sports_analytics/events.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/events.py)
- [sports_analytics/recommendations.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/recommendations.py)
- [sports_analytics/pipeline.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/pipeline.py)
- [dashboard.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/dashboard.py)

### Definition of done

- Users can look at one session and understand what the model thinks happened.
- Graphs reflect real tracked motion instead of sparse refresh data.
- Coaching tips still appear when the last frame is not the best frame.

## 7. Basketball After Volleyball

Goal:
Add basketball after the platform is ready for more complex team interaction logic.

### Why basketball should wait

- More players on court.
- More occlusion.
- More possession-like reasoning.
- More frequent ball loss and re-acquisition.
- Dribbling and pass logic depend on better temporal reasoning than the current heuristics support cleanly.

### Expected v1 basketball scope later

- `dribble_window`
- `pass_candidate`
- `shot_attempt_window`
- `rebound_candidate`
- `drive_candidate`

This should start only after the multi-camera Level-1 structure and the inference-quality sprint are stable.

## 8. Recommended Build Order

1. Volleyball profile and baseline support
2. Volleyball event engine
3. Volleyball recommendations and dashboard support
4. Multi-camera Level 1 metadata and storage model
5. Multi-camera launch flow and grouped dashboard view
6. Inference quality sprint
7. Basketball planning pass

## 9. Suggested Sprint Breakdown

### Sprint A

- Add volleyball to profiles and dashboard selectors
- Add volleyball event engine skeleton
- Add volleyball-specific recommendation hooks
- Add volleyball support docs

Acceptance criteria:

- A volleyball session can run through the system.
- The dashboard shows volleyball as a supported sport.

### Sprint B

- Improve volleyball event heuristics
- Add volleyball graphs and inference summaries
- Add validation clip coverage

Acceptance criteria:

- Volleyball produces visible event and coaching output on at least one real clip.

### Sprint C

- Introduce `match_id` and `camera_id`
- Add grouped session discovery
- Add side-by-side multi-camera dashboard view

Acceptance criteria:

- Two camera sessions can be reviewed together under one match.

### Sprint D

- Inference quality pass across all sports
- Better graphs
- Better recommendation visibility

Acceptance criteria:

- Results feel more informative and less empty across real sessions.

## 10. Immediate Next Coding Task

The best next code task is:

1. Add `volleyball` to [sports_analytics/profiles.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/profiles.py)
2. Add a `VolleyballEventEngine` to [sports_analytics/events.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/events.py)
3. Add volleyball recommendations to [sports_analytics/recommendations.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/recommendations.py)
4. Expose volleyball in [dashboard.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/dashboard.py)

That gives the fastest visible product progress while keeping the architecture clean.
