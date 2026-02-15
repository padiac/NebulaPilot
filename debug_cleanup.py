
import os
from pathlib import Path

# Use the Google Drive path from previous runs
source_dir = r"C:\Users\pppad\My Drive\N.I.N.A"
IGNORED_FILES = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}

print(f"Scanning for empty/junk directories in: {source_dir}")

for root, dirs, files in os.walk(source_dir, topdown=False): # Bottom up
    root_path = Path(root)
    if root_path == Path(source_dir):
        continue # Don't analyze root itself yet

    # Check contents
    current_files = set(files)
    current_dirs = set(dirs) # Should be empty if bottom-up worked correctly on leaves
    
    # Real files (non-junction)
    real_files = current_files - IGNORED_FILES
    
    if not real_files and not current_dirs:
        print(f"\n[CANDIDATE FOR DELETION] {root_path}")
        print(f"   Files inside: {list(current_files)}")
    elif not real_files and current_dirs:
        print(f"\n[CONTAINER FOLDER] {root_path}")
        print(f"   Contains empty subdirs? {list(current_dirs)}")
    else:
        # Has real files
        # print(f"[KEPT] {root_path} has {len(real_files)} real files.")
        pass
