# Demo Day Checklist

Use this on the exact machine and network you plan to present from.

## 1. Startup

Run the quick smoke check:

```powershell
.\demo_run.ps1 -Mode smoke -Sport tennis -Port 8530
```

Then start the dashboard normally:

```powershell
python -m streamlit run dashboard.py --server.port 8530
```

Open:

- `http://localhost:8530`

## 2. Launch Page Checks

From the dashboard:

1. Open `Launch`
2. Choose `cricket`
3. Select `local file`
4. Pick `data/models/scripts/cricket.mp4`
5. Click `Start Analysis`

Confirm:

- job status changes to `Running`
- command preview looks correct
- `Recent Job Log` appears
- `selected session` flips to latest

When it completes, confirm:

- status changes to `Completed`
- a new session appears in history
- the new session has `preview.jpg` and `output.mp4`

## 3. Upload Check

From `Launch`:

1. Select `upload`
2. Upload one known-good short video
3. Choose the matching sport
4. Click `Start Analysis`

Confirm:

- uploaded path is shown clearly
- job starts without terminal help
- session appears in history after completion

## 4. Live Webcam Check

From `Live`:

1. Select `webcam`
2. Use source `0` unless your camera needs another index
3. Choose the sport profile
4. Click `Start Live Capture`

Confirm:

- job status becomes `Running`
- control-room panel shows `Source Mode: Live`
- preview frame updates
- `Session Tracking Job` shows `Yes`
- live log updates

Then click `Stop Current Job` and confirm:

- job state changes away from `Running`
- session remains browsable

## 5. RTSP Check

From `Live`:

1. Select `rtsp`
2. Paste the exact stream URL you will demo
3. Choose the sport
4. Click `Start Live Capture`

Confirm:

- the app accepts the URL
- the job starts
- preview frame updates
- notes/logs do not show repeated open failures

If this fails, do not improvise live. Switch to a recorded file demo.

## 6. Dashboard Review Check

Open `Dashboard` and confirm:

- Overview shows sport, baseline contract, and capability labels
- Motion tab renders without errors
- Recommendations tab loads
- History lists saved sessions
- Raw Data opens

## 7. Fallback Plan

If webcam or RTSP is unstable:

1. Use `Launch`
2. Select `local file`
3. Run `cricket.mp4` or `tennis.mp4`
4. Show the saved session in `Dashboard`

This is the safest presentation path.

## 8. Last-Minute Rules

- Prefer short clips over long ones if the machine is under load.
- Keep one known-good recorded clip ready per sport.
- Verify camera permissions before the audience arrives.
- If codec issues appear, use the recorded fallback immediately.
