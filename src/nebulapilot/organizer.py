
import os
import shutil
from pathlib import Path
from datetime import datetime
from astropy.io import fits
from .scanner import get_fits_metadata

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
    Mirrors the source directory structure under the target folder.
    """
    file_path = Path(metadata["path"])
    
    if not is_good:
        # Failed frames go to simplified structure or mirror structure in a failed folder
        # For consistency, let's keep failed logic simple or mirror it too?
        # Let's mirror it under 'failed'
        try:
            rel_path = file_path.relative_to(source_root)
        except ValueError:
            # Fallback if not relative (shouldn't happen if organized correct)
            rel_path = file_path.name
            
        return Path(dest_root) / "failed" / rel_path
    
    # Good frames: Target / RelPath
    target_name = metadata.get("target_name", "Unknown").replace(" ", "_").replace("/", "-")
    
    try:
        rel_path = file_path.relative_to(source_root)
    except ValueError:
         # Fallback
        rel_path = file_path.name
    
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

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        organize_directory(sys.argv[1], sys.argv[2], dry_run=True)
    else:
        print("Usage: python -m nebulapilot.organizer <source> <dest>")
