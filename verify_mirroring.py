
import os
import shutil
from pathlib import Path
import sys

# Add src to path mechanism
sys.path.append(os.path.join(os.getcwd(), "src"))

try:
    from nebulapilot.organizer import organize_directory
    # Mocking get_fits_metadata and is_frame_good to avoid astropy dependency if needed
    # But let's try real import first
    from nebulapilot.scanner import get_fits_metadata
except ImportError:
    print("Import Error: Could not import nebulapilot modules. Check PYTHONPATH.")
    sys.exit(1)

# Mocking fits functionality if astropy is missing or problematic in test env
# We'll monkeypatch get_fits_metadata for the test if it fails, but let's assume it works.
# Actually, to be safe and dependency-free, let's mock get_fits_metadata in the test script
# since we only care about the path logic in organizer.py

import nebulapilot.organizer
import nebulapilot.scanner

# Mock metadata return
def mock_get_metadata(file_path):
    name = str(file_path.name)
    target = "Unknown"
    if "TargetA" in name: target = "TargetA"
    if "TargetB" in name: target = "TargetB"
    
    return {
        "path": str(file_path),
        "target_name": target,
        "date_obs": "2026-02-11T20:00:00",
        "image_type": "LIGHT" # Not used for path anymore, but good to have
    }

# Mock is_good
def mock_is_good(header):
    return True

# Monkeypatch
nebulapilot.organizer.get_fits_metadata = mock_get_metadata
nebulapilot.organizer.is_frame_good = mock_is_good
# We also need to mock fits.open since organizer calls it to get header for is_good
from unittest.mock import MagicMock
nebulapilot.organizer.fits = MagicMock()
nebulapilot.organizer.fits.open.return_value.__enter__.return_value = MagicMock() # context manager

def test_mirroring():
    base_dir = Path("test_mirroring_env")
    source_root = base_dir / "source_root"
    dest_root = base_dir / "dest_root"
    
    # Clean up
    if base_dir.exists():
        shutil.rmtree(base_dir)
    
    # Create Source Structure
    # source_root / 2026-02-11 / LIGHT / TargetA_1.fits
    # source_root / 2026-02-11 / LIGHT / TargetB_1.fits
    # source_root / Session2 / FLAT / TargetA_Flat.fits
    
    (source_root / "2026-02-11" / "LIGHT").mkdir(parents=True)
    (source_root / "Session2" / "FLAT").mkdir(parents=True)
    
    targets = [
        (source_root / "2026-02-11" / "LIGHT" / "TargetA_1.fits"),
        (source_root / "2026-02-11" / "LIGHT" / "TargetB_1.fits"),
        (source_root / "Session2" / "FLAT" / "TargetA_Flat.fits")
    ]
    
    for p in targets:
        with open(p, "w") as f:
            f.write("mock fits data")

    print(f"Created mocked source at {source_root}")

    # Run Organizer
    print("Running organize_directory...")
    nebulapilot.organizer.organize_directory(str(source_root), str(dest_root), dry_run=False)

    # Verify Destinations
    # Logic: Dest / Target / [RelPath]
    
    # 1. TargetA_1
    # RelPath: 2026-02-11/LIGHT/TargetA_1.fits
    # Expected: dest_root / TargetA / 2026-02-11 / LIGHT / TargetA_1.fits
    expected_A1 = dest_root / "TargetA" / "2026-02-11" / "LIGHT" / "TargetA_1.fits"
    
    # 2. TargetB_1
    # RelPath: 2026-02-11/LIGHT/TargetB_1.fits
    # Expected: dest_root / TargetB / 2026-02-11 / LIGHT / TargetB_1.fits
    expected_B1 = dest_root / "TargetB" / "2026-02-11" / "LIGHT" / "TargetB_1.fits"
    
    # 3. TargetA_Flat
    # RelPath: Session2/FLAT/TargetA_Flat.fits
    # Expected: dest_root / TargetA / Session2 / FLAT / TargetA_Flat.fits
    expected_A_Flat = dest_root / "TargetA" / "Session2" / "FLAT" / "TargetA_Flat.fits"

    passed = True
    for p in [expected_A1, expected_B1, expected_A_Flat]:
        if p.exists():
            print(f"[OK] Found {p}")
        else:
            print(f"[FAIL] Missing {p}")
            passed = False
            
    if passed:
        print("\nSUCCESS: All files mirrored under correct Targets!")
    else:
        print("\nFAILURE: Some files missing.")

if __name__ == "__main__":
    test_mirroring()
