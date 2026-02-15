
import os
import shutil
from pathlib import Path
from datetime import datetime
from astropy.io import fits
from .scanner import get_fits_metadata

import re

def get_path_from_date_folder(file_path):
    """
    Try to find a date-like folder in the path and return the relative path starting from there.
    Supports YYYY-MM-DD, YYYYMMDD, YYYY_MM_DD.
    """
    parts = list(file_path.parts)
    # Regex for YYYY-MM-DD, YYYYMMDD, YYYY_MM_DD (simple validation)
    # Matches years 20xx or 19xx
    date_pattern = re.compile(r'^(19|20)\d{2}[-_\.]?(0[1-9]|1[0-2])[-_\.]?(0[1-9]|[12]\d|3[01])$')
    
    for i, part in enumerate(parts):
        if date_pattern.match(part):
            # Found the date folder. Return path starting from this part.
            return Path(*parts[i:])
            
    return None

def is_frame_good(header):
    """
    Check if a frame is good enough to be kept.
    Currently returns True for all valid FITS files.
    """
    # Example logic:
    # if header.get("EXPTIME", 0) < 60:
    #     return False
    return True

def get_organize_path(metadata, dest_root, source_root, is_good):
    """
    Determine the destination path for a file based on its metadata.
    Preserves directory structure starting from the Date folder downwards.
    """
    file_path = Path(metadata["path"])
    
    # Determine the structural part of the path we want to keep
    # Strategy: "Date Downwards"
    rel_path = get_path_from_date_folder(file_path)
    
    if rel_path is None:
        # Fallback: If no date folder found, try relative to source_root, else just filename
        try:
            rel_path = file_path.relative_to(source_root)
        except ValueError:
            rel_path = Path(file_path.name)
            
    if not is_good:
        return Path(dest_root) / "failed" / rel_path
    
    # Good frames: Target / RelPath
    target_name = metadata.get("target_name", "Unknown").replace(" ", "_").replace("/", "-")
    
    return Path(dest_root) / target_name / rel_path


from .db import init_db, add_target, add_frame

def organize_directory(source_dir, dest_dir, dry_run=False):
    """
    Move FITS files from source_dir to dest_dir, organized by Target/(SourceStructure).
    Updates the database with the new location and progress.
    """
    source_path = Path(source_dir)
    dest_path = Path(dest_dir)
    
    if not dry_run:
        init_db()
    
    if not source_path.exists():
        print(f"Source directory {source_dir} does not exist.")
        return

    print(f"Scanning {source_dir}...")
    
    for file_path in source_path.rglob("*.fit*"):
        if not file_path.is_file():
            continue
            
        try:
            # We need the raw header for filtering logic if we implement strict rules
            # For now, we reuse get_fits_metadata for convenience
            metadata = get_fits_metadata(file_path)
            
            if not metadata:
                print(f"Skipping {file_path}: Could not read metadata")
                continue

            # In a real implementation we might want to read header again if is_frame_good needs more than metadata dict
            # For now let's assume is_frame_good takes the header from a quick open or we trust the metadata
            # Let's open briefly to check the header for is_frame_good
            with fits.open(file_path) as hdul:
                header = hdul[0].header
                is_good = is_frame_good(header)
                
            dest_file_path = get_organize_path(metadata, dest_dir, source_dir, is_good)
            
            if dry_run:
                print(f"[DRY RUN] Would move {file_path.name} -> {dest_file_path}")
            else:
                dest_file_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), str(dest_file_path))
                print(f"Moved {file_path.name} -> {dest_file_path}")
                
                # Update DB
                # 1. Update Path in metadata to new location
                metadata["path"] = str(dest_file_path)
                # 2. Ensure target exists
                add_target(metadata["target_name"])
                # 3. Add frame record
                add_frame(metadata)
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    # Clean up empty source directories after moving files
    if not dry_run:
        print("Cleaning up empty source directories...")
        for root, dirs, files in os.walk(source_dir, topdown=False):
            for name in dirs:
                dir_to_check = Path(root) / name
                try:
                    # Check if directory is empty (no files or subdirs)
                    # iterdir() might raise if permission denied, hence try/except
                    if not any(dir_to_check.iterdir()):
                        dir_to_check.rmdir()
                        print(f"Removed empty directory: {dir_to_check}")
                except Exception as e:
                    pass # Ignore errors (e.g. non-empty, permission)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        organize_directory(sys.argv[1], sys.argv[2], dry_run=True)
    else:
        print("Usage: python -m nebulapilot.organizer <source> <dest>")
