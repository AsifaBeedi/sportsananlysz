# Performance Notes

These notes are intentionally practical rather than over-precise. The project has not been benchmarked rigorously yet.

## What To Expect

- CPU-only runs work for startup checks, short validation passes, and recorded-video demos.
- Longer recorded videos can still take noticeable time on CPU-only machines.
- Live webcam and RTSP analysis are much more comfortable on a machine with GPU acceleration.
- Hockey is usually the most fragile workload because puck tracking is a small-object problem.

## Current Reality

- The project uses YOLO-based detection and pose models from `ultralytics`.
- Some bundled demo videos can trigger codec noise in certain environments.
- The pipeline includes a safe demo fallback path for unstable demo assets, so a broken demo file does not have to kill the whole run.

## Recommended Usage

- For quick confidence checks: run `python tools/smoke_test.py`.
- For short demos on modest hardware: use `--max-frames` and a recorded source.
- For longer dashboard sessions: prefer a machine with GPU support if available.
- For live capture demos: verify the camera or RTSP stream separately before presenting.
- On Windows machines with OpenH264 noise, prefer `--writer-codec mp4v`.
- For the fastest validation path, use `--no-output-video` so the run skips `output.mp4` entirely.

## CPU vs GPU Guidance

### CPU-only

- Best for development, smoke tests, and short recordings.
- Expect slower frame throughput on longer sessions.
- Use headless mode when validating from the terminal:

```bash
python data/models/scripts/detects_players.py --sport tennis --source-type demo --no-display --no-output-video --writer-codec mp4v --max-frames 10
```

- The pipeline now throttles preview/stats disk writes instead of rewriting them on every single frame, which helps on slower Windows machines.

### GPU-enabled

- Better for live demos and longer sessions.
- Better chance of smoother end-to-end dashboard monitoring.
- Still validate the exact machine and codecs before a presentation.

## Known Runtime Risks

- Detached background jobs still deserve a manual browser-level check before a live presentation.
- Codec support can vary by machine, especially for bundled demo assets.
- H.264 browser-friendly output is not guaranteed on every Windows machine unless a compatible encoder is installed.
- The dashboard is strong as a control surface, but live mode should still be treated as "verify before demo day", not "assume perfect forever".
