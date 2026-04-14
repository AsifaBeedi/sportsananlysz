# FINAL_FIX.py - Run this ONCE

import json
from pathlib import Path

print("=" * 60)
print("FINAL FIX - FOR YOUR ACTUAL STRUCTURE")
print("=" * 60)

# Your JSON is in root
json_path = Path("match_stats.json")

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Fix paths - YOUR files are in data/review_frames and data/snippets
data["preview_frame_path"] = "latest_annotated_frame.jpg"
data["output_video_path"] = "annotated_match_output.mp4"

# Fix bad frames paths
bad_frames_fixed = []
for frame in data.get("clip_summary", {}).get("bad_frames", []):
    old_path = frame.get("frame_path", "")
    filename = Path(old_path).name
    # Clean up the filename
    filename = filename.replace("__", "_")
    filename = filename.replace("___", "_")
    filename = filename.replace("\u2013", "-")
    # Files are in data/review_frames/
    frame["frame_path"] = f"data/review_frames/{filename}"
    bad_frames_fixed.append(frame)
    print(f"  Fixed: data/review_frames/{filename}")

data["clip_summary"]["bad_frames"] = bad_frames_fixed

# Fix snippet paths
snippet_index_fixed = {}
for metric, clips in data.get("clip_summary", {}).get("snippet_index", {}).items():
    fixed_clips = []
    for clip_path in clips:
        filename = Path(clip_path).name
        filename = filename.replace("__", "_")
        filename = filename.replace("___", "_")
        # Files are in data/snippets/
        fixed_clips.append(f"data/snippets/{filename}")
    snippet_index_fixed[metric] = fixed_clips
    print(f"  Fixed {len(fixed_clips)} clips for {metric}")

data["clip_summary"]["snippet_index"] = snippet_index_fixed

# Save
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("\n✅ JSON fixed!")

# Verify files exist
print("\n" + "=" * 60)
print("VERIFYING FILES:")
print("=" * 60)

# Check review_frames
review_dir = Path("data/review_frames")
if review_dir.exists():
    jpgs = list(review_dir.glob("*.jpg"))
    print(f"✅ data/review_frames/ - {len(jpgs)} JPG files")
    for f in jpgs[:3]:
        print(f"    {f.name}")
else:
    print(f"❌ data/review_frames/ not found!")

# Check snippets
snippets_dir = Path("data/snippets")
if snippets_dir.exists():
    mp4s = list(snippets_dir.glob("*.mp4"))
    print(f"✅ data/snippets/ - {len(mp4s)} MP4 files")
    for f in mp4s[:3]:
        print(f"    {f.name}")
else:
    print(f"❌ data/snippets/ not found!")

# Check preview
preview = Path("latest_annotated_frame.jpg")
if preview.exists():
    print(f"✅ latest_annotated_frame.jpg")
else:
    print(f"⚠️ latest_annotated_frame.jpg not found")

# Check output
output = Path("annotated_match_output.mp4")
if output.exists():
    print(f"✅ annotated_match_output.mp4")
else:
    print(f"⚠️ annotated_match_output.mp4 not found")

print("\n" + "=" * 60)
print("🎉 RUN: streamlit run dashboard.py")
print("=" * 60)