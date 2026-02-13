import os
import time
from pathlib import Path
from astropy.io import fits
from .db import add_frame, add_target, get_targets

def normalize_filter(filter_name):
    """Normalize filter names to L, R, G, B, S, H, O."""
    name = filter_name.upper().strip()
    
    if name in ["L", "LUM", "LUMINANCE"]:
        return "L"
    if name in ["R", "RED"]:
        return "R"
    if name in ["G", "GREEN"]:
        return "G"
    if name in ["B", "BLUE"]:
        return "B"
    
    # Narrowband
    if any(x in name for x in ["HA", "H-ALPHA", "H_ALPHA"]):
        return "H"
    if any(x in name for x in ["OIII", "O3", "O-III"]):
        return "O"
    if any(x in name for x in ["SII", "S2", "S-II"]):
        return "S"
        
    return name

def get_fits_metadata(file_path):
    try:
        with fits.open(file_path) as hdul:
            header = hdul[0].header
            
            # Common astronomical FITS keywords
            target = header.get("OBJECT", "Unknown")
            raw_filter = header.get("FILTER", "Unknown")
            filter_name = normalize_filter(raw_filter)
            
            exptime = header.get("EXPTIME", header.get("EXPOSURE", 0))
            date_obs = header.get("DATE-OBS", "Unknown")
            
            return {
                "path": str(file_path),
                "target_name": target,
                "filter": filter_name,
                "exptime_sec": float(exptime),
                "date_obs": date_obs,
                "fwhm": None, # Future calculation
                "eccentricity": None, # Future calculation
                "star_count": None, # Future calculation
                "background": None, # Future calculation
                "decision": "APPROVED",
                "score": 1.0
            }
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def is_file_stable(file_path, wait_time=2):
    """Check if file size is stable (not currently being written)."""
    size1 = os.path.getsize(file_path)
    time.sleep(wait_time)
    size2 = os.path.getsize(file_path)
    return size1 == size2

def scan_directory(directory_path):
    path = Path(directory_path)
    if not path.exists():
        print(f"Directory {directory_path} does not exist.")
        return

    # Get known targets to automatically add new ones if found
    known_targets = {t["name"] for t in get_targets()}

    for file_path in path.rglob("*.fit*"): # Matches .fit, .fits, .fts
        if not file_path.is_file():
            continue
            
        # Basic stability check
        # In a real app, we might check mtime or keep track of seen files
        metadata = get_fits_metadata(file_path)
        if metadata:
            if metadata["target_name"] not in known_targets:
                add_target(metadata["target_name"])
                known_targets.add(metadata["target_name"])
            
            add_frame(metadata)
            print(f"Scanned: {file_path.name} ({metadata['target_name']} - {metadata['filter']})")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        scan_directory(sys.argv[1])
    else:
        print("Usage: python -m nebulapilot.scanner <directory>")
