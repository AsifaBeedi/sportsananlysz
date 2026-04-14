# rename_files.py - Run this ONCE to fix filename mismatches

import os
from pathlib import Path

# Your review_frames folder
review_frames_dir = Path("data/review_frames")

if not review_frames_dir.exists():
    print(f"❌ Folder not found: {review_frames_dir}")
    exit(1)

print(f"✅ Found folder: {review_frames_dir}")
print("=" * 60)

# Rename files from single underscore to double underscore
renamed_count = 0
for file_path in review_frames_dir.glob("*.jpg"):
    old_name = file_path.name
    
    # Convert single underscore to double underscore
    # tennis-1776152758_000117_Low_Posture_Score_(59)_Player_1.jpg
    # becomes:
    # tennis-1776152758__000117__Low_Posture_Score_(59)__Player_1.jpg
    
    new_name = old_name.replace("_", "__")
    
    # Fix the special case with parentheses
    new_name = new_name.replace("(", "(").replace(")", ")")
    
    if new_name != old_name:
        new_path = file_path.parent / new_name
        file_path.rename(new_path)
        print(f"✓ Renamed: {old_name}")
        print(f"       to: {new_name}")
        renamed_count += 1

print("=" * 60)
print(f"✅ Renamed {renamed_count} files")

# Also rename files in snippets folder if needed
snippets_dir = Path("data/snippets")
if snippets_dir.exists():
    print("\n" + "=" * 60)
    print("Checking snippets folder...")
    renamed_snippets = 0
    for file_path in snippets_dir.glob("*.mp4"):
        old_name = file_path.name
        new_name = old_name.replace("_", "__")
        if new_name != old_name:
            new_path = file_path.parent / new_name
            file_path.rename(new_path)
            print(f"✓ Renamed: {old_name}")
            print(f"       to: {new_name}")
            renamed_snippets += 1
    print(f"✅ Renamed {renamed_snippets} snippet files")

print("\n" + "=" * 60)
print("🎉 DONE! Now restart Streamlit:")
print("   streamlit run dashboard.py")