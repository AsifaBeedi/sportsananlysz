# fix_paths.py
import json
from pathlib import Path

stats_path = Path("data/models/scripts/match_stats.json")

with open(stats_path, "r") as f:
    data = json.load(f)

# Fix bad frame paths
for frame in data["clip_summary"]["bad_frames"]:
    old = frame["frame_path"]
    filename = Path(old).name
    frame["frame_path"] = f"review_frames/{filename}"
    print(f"Fixed: {filename}")

# Fix snippet paths
new_index = {}
for metric, clips in data["clip_summary"]["snippet_index"].items():
    new_clips = []
    for clip in clips:
        filename = Path(clip).name
        new_clips.append(f"snippets/{filename}")
    new_index[metric] = new_clips
data["clip_summary"]["snippet_index"] = new_index

# Save
with open(stats_path, "w") as f:
    json.dump(data, f, indent=2)

print("Done!")