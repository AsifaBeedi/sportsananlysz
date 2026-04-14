# Presentation Flow

This is a simple final-demo script for presenting the project clearly and confidently.

## 1. Opening

Start with:

"This project is a sport-agnostic sports CCTV analysis system. The core pipeline stays common across sports, and sport-specific logic is layered on top. Our current full demo is built with the tennis profile."

## 2. Explain The Problem

Use a short framing like:

- Manual sports video analysis takes time.
- Coaches and analysts want structured insights, not just raw footage.
- A CCTV-style analytics system can automate tracking, biomechanics signals, event detection, and feedback generation.

## 3. Explain The Architecture

Walk through the pipeline in this order:

1. Video input
2. Object detection
3. Player tracking
4. Ball tracking
5. Pose estimation
6. Posture analysis
7. Event detection
8. Racket swing analysis
9. Ball speed estimation
10. Recommendation engine
11. Dashboard visualization

Key line to say:

"The important design choice is that the pipeline core is reusable, while the sport rules are pluggable through profiles like tennis, cricket, baseball, and hockey."

## 4. Run The Demo

Terminal 1:

```bash
python data/models/scripts/detects_players.py --sport tennis --video data/models/scripts/tennis.mp4
```

Terminal 2:

```bash
streamlit run dashboard.py
```

If you need a safer fallback for class/demo timing, use:

```bash
python data/models/scripts/detects_players.py --sport tennis --video data/models/scripts/tennis.mp4 --no-display --max-frames 20
```

## 5. What To Show During The Demo

Point out these dashboard areas:

- live player count
- ball speed
- posture score
- swing and contact counts
- event timeline
- racket path summary
- coaching recommendations
- runtime session history

Good line to use:

"We are not just detecting players. We are converting video into structured sports analytics."

## 6. Multi-Sport Story

Be explicit here because this is an assessment strength:

- Tennis is the completed demo profile.
- The architecture is sport-agnostic.
- The same core can run with other sport profiles.
- Cricket, baseball, and hockey are already represented in the profile layer.
- Those profiles can be expanded with stronger object models and sport-specific event logic later.

## 7. Honest Limitations

Say this clearly if asked:

- Tennis is currently the most complete and best-tested profile.
- Cross-sport support is architectural right now, not equally optimized in accuracy.
- Some advanced recognition is heuristic because there is no labeled training dataset in this project.
- Racket tracking is currently proxy-based.

This honesty usually strengthens the presentation.

## 8. Final Closing

Close with:

"So the final outcome is a reusable sports analytics framework with a working tennis demo that performs tracking, pose analysis, event detection, speed analysis, and coaching feedback, while staying ready for multi-sport expansion."

## 9. If The Panel Asks What You Would Do Next

Answer with any of these:

- train sport-specific detectors for ball, racket, bat, and puck
- save sessions for long-term player comparison
- improve shot classification with labeled video data
- calibrate camera scale for more accurate real-world metrics
- add separate dashboards for coaches, analysts, and players
