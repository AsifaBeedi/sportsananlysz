# fix_json.py - Fix paths to match your actual filenames

import json
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
                # Get the filename
                old_path = frame["frame_path"]
                filename = Path(old_path).name
                
                # Convert double underscore to single underscore
                filename = filename.replace("__", "_")
                
                # Also remove any extra patterns
                filename = filename.replace("_-_", "_")
                
                # Set the corrected path (pointing to review_frames folder)
                frame["frame_path"] = f"review_frames/{filename}"
                print(f"Fixed frame path: {filename}")
    
    # Fix snippet_index paths
    if "snippet_index" in clip:
        new_snippet_index = {}
        for metric, clips in clip["snippet_index"].items():
            new_clips = []
            for clip_path in clips:
                filename = Path(clip_path).name
                # Fix any double underscores in video filenames too
                filename = filename.replace("__", "_")
                new_clips.append(f"snippets/{filename}")
                print(f"Fixed clip: {filename}")
            new_snippet_index[metric] = new_clips
        clip["snippet_index"] = new_snippet_index

# Save the fixed JSON
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("\n" + "="*50)
print("✅ Fixed JSON paths successfully!")
print("="*50)
print(f"Preview frame: {data.get('preview_frame_path')}")
print(f"Output video: {data.get('output_video_path')}")
print(f"Bad frames: {len(data.get('clip_summary', {}).get('bad_frames', []))}")
print(f"Snippets: {data.get('clip_summary', {}).get('snippet_count', 0)}")
print("\nNow restart Streamlit: streamlit run dashboard.py")