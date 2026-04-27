For **Person 2: Biomechanics & Analytics**, we have done a lot of the core logic, but the deliverable is not yet packaged exactly in the structure you listed.

Status: **about 65 percent done**

| Phase | Status |
|---|---|
| Phase 1: Data ingestion | Partial |
| Phase 2: Joint angle engine | Mostly done |
| Phase 3: Posture risk detection | Mostly done |
| Phase 4: Frame flagging | Mostly done |
| Phase 5: Risk scoring | Partial |
| Phase 6: Summary analytics | Partial |
| Phase 7: `risk_data.json` | Pending |
| Phase 8: Integration | Partial |

**Done**
- Keypoints are extracted and mapped.
- Elbow angles exist.
- Knee angles exist.
- Hip angles exist.
- Trunk lean exists.
- Low posture / knee-load style rule exists.
- Forward trunk lean rule exists.
- Arm overextension rule exists.
- Left/right imbalance rule exists.
- Risk labels exist internally.
- Risky frames are saved.
- Review frames exist.
- Dashboard can display posture/risk information.

**Partial**
- No separate `pose_data.json`; pose data is inside the session stats JSON.
- Shoulder angle is not cleanly implemented as its own explicit output.
- Risk score exists as posture/risk level logic, but not the exact `+30/+60/+90` frame-level scoring.
- Summary analytics exist partly, but not exactly as `total risky frames`, `most common risk`, `highest risk frame`, `average risk score`.
- Dashboard reads existing stats, not a dedicated `risk_data.json`.

**Pending for Person 2**
- Create `src/biomechanics/risk_engine.py`
- Create `src/biomechanics/frame_flagger.py`
- Create final `outputs/risk_data.json`
- Store frame-wise risk entries in the requested format
- Add explicit shoulder angle calculation
- Add exact frame-level score:
  - 1 risk = 30
  - 2 risks = 60
  - 3 risks = 90
- Add risk levels:
  - 0-30 Low
  - 31-60 Medium
  - 61-100 High
- Add summary:
  - total frames
  - risky frames
  - average risk
  - highest risk
  - most common risk

**Pending Tasks Split for 3 People**

**Person 1: Video + CV Pipeline**
- Export clean `pose_data.json`
- Ensure every frame has mapped keypoints
- Ensure frame index is consistent with output video
- Ensure processed video is saved to `outputs/processed_video.mp4`
- Confirm skeleton and boxes appear clearly
- Confirm `models/yolov8n.pt` and `models/yolov8n-pose.pt` are used from the new folder

**Person 2: Biomechanics + Analytics**
- Build `risk_engine.py`
- Build `frame_flagger.py`
- Add shoulder angle calculation
- Convert current posture rules into clean risk rules
- Generate `outputs/risk_data.json`
- Save risky frames into `outputs/review_frames/`
- Add exact risk scoring and risk levels
- Add summary analytics

**Person 3: Dashboard + Integration**
- Load `outputs/risk_data.json`
- Show total frames, risky frames, average risk, highest risk
- Show risk table by frame
- Display review frames from `outputs/review_frames/`
- Add JSON download button
- Add processed video download button
- Make sure dashboard works from `app/streamlit_app.py`
- Keep Tennis/Badminton/Table Tennis dashboard routing clean

**Most Important Next Step**

Do this next:

```text
Person 2 creates risk_data.json.
```

That is the biggest missing piece. Once that exists, Person 3 can plug it into the dashboard very quickly.