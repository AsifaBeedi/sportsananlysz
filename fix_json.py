# fix_json.py - Run this to fix paths in your JSON without losing data

import json
import re
from pathlib import Path

# Load your original JSON
json_path = Path("data/models/scripts/match_stats.json")

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Fix preview_frame_path
if "preview_frame_path" in data:
    data["preview_frame_path"] = "latest_annotated_frame.jpg"

# Fix output_video_path
if "output_video_path" in data:
    data["output_video_path"] = "annotated_match_output.mp4"

# Fix clip_summary paths
if "clip_summary" in data:
    clip = data["clip_summary"]
    
    # Fix bad_frames paths
    if "bad_frames" in clip:
        for frame in clip["bad_frames"]:
            if "frame_path" in frame:
                # Extract just the filename
                old_path = frame["frame_path"]
                filename = Path(old_path).name
                # Clean up the filename (remove unicode dash etc.)
                filename = filename.replace("\u2013", "_").replace("–", "_")
                frame["frame_path"] = f"review_frames/{filename}"
    
    # Fix snippet_index paths
    if "snippet_index" in clip:
        new_snippet_index = {}
        for metric, clips in clip["snippet_index"].items():
            new_clips = []
            for clip_path in clips:
                filename = Path(clip_path).name
                new_clips.append(f"snippets/{filename}")
            new_snippet_index[metric] = new_clips
        clip["snippet_index"] = new_snippet_index

# Save the fixed JSON (preserving ALL original data)
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("✅ Fixed JSON paths successfully!")
print(f"   Preview frame: {data.get('preview_frame_path')}")
print(f"   Output video: {data.get('output_video_path')}")
print(f"   Bad frames: {len(data.get('clip_summary', {}).get('bad_frames', []))}")
print(f"   Snippets: {data.get('clip_summary', {}).get('snippet_count', 0)}")