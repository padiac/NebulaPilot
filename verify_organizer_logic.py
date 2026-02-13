
import sys
from pathlib import Path
sys.path.append("src")

from nebulapilot.organizer import get_organize_path

def test_organization_logic():
    print("Testing Organization Logic...")
    
    # Test 1: Good Frame
    metadata_good = {
        "path": "/data/incoming/frame1.fits",
        "target_name": "M 42",
        "date_obs": "2023-10-27T12:00:00",
        "filter": "L"
    }
    path_good = get_organize_path(metadata_good, "/data/organized", is_good=True)
    expected_good = Path("/data/organized/M_42/2023-10-27/frame1.fits")
    
    if path_good == expected_good:
        print(f"[PASS] Good Frame: {path_good}")
    else:
        print(f"[FAIL] Good Frame: Expected {expected_good}, got {path_good}")

    # Test 2: Bad Frame
    metadata_bad = {
        "path": "/data/incoming/frame2.fits",
        "target_name": "M 31",
        "date_obs": "2023-10-28T12:00:00",
        "filter": "R"
    }
    path_bad = get_organize_path(metadata_bad, "/data/organized", is_good=False)
    expected_bad = Path("/data/organized/failed/2023-10-28/frame2.fits")
    
    if path_bad == expected_bad:
        print(f"[PASS] Bad Frame: {path_bad}")
    else:
        print(f"[FAIL] Bad Frame: Expected {expected_bad}, got {path_bad}")

if __name__ == "__main__":
    test_organization_logic()
