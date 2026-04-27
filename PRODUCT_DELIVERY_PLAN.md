# Product Delivery Plan

This document is the working execution plan for turning the current prototype into a usable sports analysis product.

The existing [IMPLEMENTATION_CHECKLIST.md](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/IMPLEMENTATION_CHECKLIST.md) tracks the original prototype phases.
This file tracks what still needs to be done for real product readiness.

## 1. Current Reality

What is already true in the codebase:

- The project has a real shared analytics core in [sports_analytics](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics).
- The pipeline supports per-session output folders, background runs, and unified source handling in [sports_analytics/pipeline.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/pipeline.py), [sports_analytics/session_io.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/session_io.py), and [sports_analytics/input_sources.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/input_sources.py).
- The CLI supports `file`, `demo`, `webcam`, and `rtsp` sources through `--source-type` and `--source` in [data/models/scripts/detects_players.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/data/models/scripts/detects_players.py).
- The dashboard can launch and stop analysis jobs, browse sessions, and monitor live capture status in [dashboard.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/dashboard.py) and [sports_analytics/run_control.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/run_control.py).
- Tennis, cricket, baseball, and hockey all have explicit event-engine paths in [sports_analytics/events.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/events.py), with honest capability labels exposed in the dashboard.
- Some bundled demo assets still need better validation, so the project includes a safe demo fallback path for unstable demo files in [sports_analytics/input_sources.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/sports_analytics/input_sources.py).
- The repo now includes a truthful support matrix, payload validation, smoke tests, performance notes, and a PowerShell demo helper in [SPORT_SUPPORT.md](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/SPORT_SUPPORT.md), [tools/validate_session_payload.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/tools/validate_session_payload.py), [tools/smoke_test.py](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/tools/smoke_test.py), [PERFORMANCE_NOTES.md](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/PERFORMANCE_NOTES.md), and [demo_run.ps1](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/demo_run.ps1).

## 2. Product Goal

We want one system that can:

- analyze uploaded sports videos
- analyze live sports capture
- support multiple sports through one shared platform
- keep session outputs separate and organized
- show users a clean dashboard with controls and results
- expand sport-specific intelligence without rewriting the whole system

## 3. Delivery Principles

- Build the ingestion and session architecture first.
- Separate "all sports are analyzable" from "all sports have deep sport-specific intelligence".
- Keep the core shared and isolate sport-specific logic behind clear interfaces.
- Make each milestone demoable before starting the next one.
- Prefer milestone checklists with clear acceptance criteria.

## 4. Milestones

### Milestone 0: Truth, Cleanup, and Stability

Goal:
Create a clean base we can safely build on.

- [x] Add `requirements.txt` or `pyproject.toml`.
- [x] Remove misleading references and broken commands in the dashboard.
- [x] Document the real current support level per sport.
- [x] Add a lightweight smoke-test path for startup and a short validation run.
- [x] Standardize naming for sessions, outputs, and source types.

Definition of done:

- A new developer can install dependencies and start the project from docs only.
- The dashboard does not instruct users to run non-existent commands.
- The codebase has one truthful project roadmap and one truthful run guide.

### Milestone 1: Session Architecture

Goal:
Move from one shared output file to isolated per-run sessions.

- [x] Create a session directory structure such as `data/sessions/<session_id>/`.
- [x] Store `stats.json`, `preview.jpg`, `output.mp4`, snippets, and review frames per session.
- [x] Refactor `SessionWriter` to write session-local outputs.
- [x] Update the pipeline to include session metadata consistently.
- [x] Add session discovery utilities so the dashboard can list previous runs.

Definition of done:

- Running two different analyses does not overwrite each other's outputs.
- Each session can be opened independently from the dashboard.
- The pipeline still works end to end for at least the current tennis demo.

### Milestone 2: Unified Input Layer

Goal:
Support multiple input types through one interface.

- [x] Define input source types: uploaded file, local demo file, webcam, and RTSP/IP stream.
- [x] Refactor the pipeline runner so it can open sources by type, not only by file path.
- [x] Add source metadata into session output.
- [x] Add source validation and clear user-facing error messages.
- [x] Keep one code path for frame processing after the source is opened.

Definition of done:

- The same processing pipeline can run against file and live sources.
- Source-specific code is isolated to ingestion/opening logic.
- Errors like missing camera, bad RTSP URL, or invalid file are surfaced clearly.

### Milestone 3: Dashboard Control Center

Goal:
Turn the dashboard into the place where users start and manage analysis.

- [x] Replace the current upload-only flow with upload plus analyze.
- [x] Add sport selection before starting analysis.
- [x] Add source selection: upload, demo file, webcam, RTSP.
- [x] Add start, stop, and current-session status controls.
- [x] Add previous-session browsing and session switching.
- [x] Break large dashboard sections into smaller helper modules or components.

Definition of done:

- A user can upload a video and start analysis from the UI.
- A user can start a live source from the UI.
- A user can open current and previous sessions without touching the terminal.

### Milestone 4: All-Sport Baseline Analytics

Goal:
Make every supported sport produce a useful baseline result, even before advanced sport-specific event logic.

- [x] Define a minimum baseline output for every sport.
- [x] Ensure player tracking works across all target sports.
- [x] Ensure object tracking works for each sport's primary object where feasible.
- [x] Ensure pose and posture remain available where person visibility is sufficient.
- [x] Update the dashboard to display baseline analytics even when advanced events are unavailable.
- [x] Mark unsupported advanced metrics explicitly instead of silently implying support.

Definition of done:

- Tennis, cricket, baseball, and hockey all run through the system without pretending to have the same depth.
- The dashboard clearly distinguishes baseline analytics from advanced sport-specific analytics.

### Milestone 5: Sport-Specific Intelligence

Goal:
Deepen analytics one sport at a time without destabilizing the shared platform.

#### Tennis

- [x] Stabilize current tennis event logic.
- [x] Improve contact detection quality.
- [x] Improve recommendation quality and reduce noisy advice.
- [x] Add focused validation clips for tennis scenarios.

#### Cricket

- [x] Add cricket-specific event engine.
- [x] Add bat-side motion or bat proxy logic.
- [x] Add coarse stroke classification.
- [x] Add cricket-specific recommendations.

#### Baseball

- [x] Add baseball-specific event engine.
- [x] Add pitch and swing windows.
- [x] Add bat-contact candidate logic.
- [x] Add baseball-specific recommendations.

#### Hockey

- [x] Improve puck tracking with a hockey-specific strategy.
- [x] Add stick-side motion or stick proxy logic.
- [x] Add possession or shot candidate heuristics.
- [x] Add hockey-specific recommendations.

Definition of done:

- Each sport has its own explicit event engine path.
- Shared analytics remain shared.
- Sport-specific outputs are honest, explainable, and testable.

### Milestone 6: Validation, Packaging, and Demo Readiness

Goal:
Make the system stable enough to demo confidently and continue extending.

- [x] Add smoke tests for startup and short runs.
- [x] Add sample validation videos per sport.
- [x] Add JSON schema or structural payload validation.
- [x] Add performance notes for CPU-only vs GPU-enabled runs.
- [x] Add a polished README with real setup and usage instructions.
- [x] Add a demo script for presentations.

Definition of done:

- The project is runnable from clean setup instructions.
- We can demo upload mode and live mode reliably.
- We can explain exactly what each sport supports today.

## 5. Recommended Build Order

This is the order I recommend we execute:

1. Milestone 0
2. Milestone 1
3. Milestone 2
4. Milestone 3
5. Milestone 4
6. Milestone 5
7. Milestone 6

Reason:

- Without session architecture, upload and live features will keep overwriting the same outputs.
- Without a unified input layer, live capture will become a one-off hack.
- Without baseline all-sport support, sport-specific work will become inconsistent and confusing in the UI.

## 6. Immediate Execution Plan

This is the first sprint I recommend we start with now.

### Sprint 1

- [x] Add truthful dependency/setup file.
- [x] Fix the upload page so it reflects the real CLI path and current status.
- [x] Introduce a session output directory model in config.
- [x] Refactor JSON, preview, and output-video writes to be session-local.
- [x] Add dashboard session picker for current and past sessions.

Sprint 1 acceptance criteria:

- We can run a tennis session without overwriting prior artifacts.
- The dashboard can open a selected session.
- The upload page no longer implies that analysis starts automatically when it does not.

### Sprint 2

- [x] Add unified source abstraction.
- [x] Add webcam capture support.
- [x] Add RTSP stream support.
- [x] Add UI controls for starting source-based analysis.

### Sprint 3

- [x] Make cricket, baseball, and hockey honest baseline modes.
- [x] Add per-sport capability labels in the dashboard.
- [x] Start the next sport-specific engine after baseline outputs are stable.

## 7. What We Should Not Do Yet

- Do not try to make all sports advanced at the same time.
- Do not keep adding features on top of the single shared `match_stats.json` model.
- Do not hide unsupported analytics behind generic labels.
- Do not mix UI orchestration and analytics logic even more tightly than they already are.

## 8. Working Rule For Checking Boxes

A checkbox only gets marked complete when:

- the code is implemented
- the flow is manually verified
- the docs match reality
- the feature works without depending on hidden manual steps

## 9. Next Task To Start

Milestones 0 through 6 now have code and documentation coverage in the repo.

The remaining work is operational rather than architectural:

1. Run a browser-level final demo pass on the exact machine and cameras that will be used live.
2. Validate the preferred upload, webcam, and RTSP sources on that environment.
3. Keep improving sport-specific quality with real labeled footage, especially for hockey and longer live sessions.

Note: player tracking, object tracking, pose/posture, dashboard launch, payload validation, and short-run smoke coverage are now in place. The main remaining risk is environment-specific demo reliability, especially codecs and live-source behavior on the final presentation machine.

## 10. Expansion Track

The next platform-expansion phase is documented in [VOLLEYBALL_MULTICAMERA_PLAN.md](/c:/Users/Asifa%20Bandulal%20Beed/Downloads/sports%20cctv%20analysis/VOLLEYBALL_MULTICAMERA_PLAN.md).

Priority order:

1. Add volleyball as the next explicit sport engine.
2. Add Level-1 multi-camera support using linked sessions under one match group.
3. Run an inference-quality sprint across all sports.
4. Plan basketball after the platform is ready for possession-heavy team logic.
