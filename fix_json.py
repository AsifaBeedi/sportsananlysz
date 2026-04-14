# fix_json.py - Updated for your actual folder structure

import json
from pathlib import Path

# Your JSON is in data/ folder now
json_path = Path("data/match_stats.json")

# If not there, check the old location
if not json_path.exists():
    json_path = Path("data/models/scripts/match_stats.json")

if not json_path.exists():
    print(f"❌ Cannot find match_stats.json")
    exit(1)

print(f"✅ Found JSON at: {json_path}")

# Load JSON
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Fix paths - point to data/review_frames and data/snippets
if "clip_summary" in data:
    # Fix bad_frames paths
    for frame in data["clip_summary"].get("bad_frames", []):
        old_path = frame.get("frame_path", "")
        filename = Path(old_path).name
        # Remove any double underscores
        filename = filename.replace("__", "_")
        # Point to data/review_frames
        frame["frame_path"] = f"data/review_frames/{filename}"
        print(f"Fixed frame: {filename}")
    
    # Fix snippet paths
    new_snippet_index = {}
    for metric, clips in data["clip_summary"].get("snippet_index", {}).items():
        new_clips = []
        for clip_path in clips:
            filename = Path(clip_path).name
            filename = filename.replace("__", "_")
            new_clips.append(f"data/snippets/{filename}")
        new_snippet_index[metric] = new_clips
    data["clip_summary"]["snippet_index"] = new_snippet_index
    print(f"Fixed snippets for {len(new_snippet_index)} metrics")

# Fix preview and output paths
data["preview_frame_path"] = "data/latest_annotated_frame.jpg"
data["output_video_path"] = "data/annotated_match_output.mp4"

# Save the fixed JSON
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("\n✅ Fixed! Your files should now be found at:")
print("   - data/review_frames/*.jpg")
print("   - data/snippets/*.mp4")
print("   - data/latest_annotated_frame.jpg")
print("\nRestart Streamlit: streamlit run dashboard.py")