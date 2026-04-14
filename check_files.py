# check_files.py
import json
from pathlib import Path

print("=" * 50)
print("FILE CHECK")
print("=" * 50)

# Check if review_frames folder exists
review_dir = Path("review_frames")
if review_dir.exists():
    print(f"\n✅ review_frames folder exists")
    jpg_files = list(review_dir.glob("*.jpg"))
    print(f"   Found {len(jpg_files)} JPG files:")
    for f in jpg_files[:5]:
        print(f"   - {f.name}")
else:
    print(f"\n❌ review_frames folder NOT found at: {review_dir.absolute()}")

# Check what JSON is looking for
json_path = Path("data/models/scripts/match_stats.json")
if json_path.exists():
    with open(json_path, "r") as f:
        data = json.load(f)
    
    print("\n" + "=" * 50)
    print("JSON is looking for:")
    print("=" * 50)
    for frame in data.get("clip_summary", {}).get("bad_frames", [])[:3]:
        frame_path = frame.get("frame_path", "")
        print(f"  - {frame_path}")
        
        # Check if this file exists
        if Path(frame_path).exists():
            print(f"    ✅ EXISTS")
        else:
            print(f"    ❌ MISSING")
            # Try to find matching file
            filename = Path(frame_path).name
            possible_match = review_dir / filename
            if possible_match.exists():
                print(f"    💡 Found at: {possible_match}")
            else:
                # Try with single underscores
                alt_filename = filename.replace("_", "__")
                alt_match = review_dir / alt_filename
                if alt_match.exists():
                    print(f"    💡 Found with double underscores: {alt_match.name}")