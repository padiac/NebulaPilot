
import os
import shutil
from pathlib import Path
from astropy.io import fits
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))
from nebulapilot.organizer import organize_directory

def create_mock_fits(filename, target, date_obs, imagetyp):
    hdu = fits.PrimaryHDU()
    hdu.header['OBJECT'] = target
    hdu.header['DATE-OBS'] = date_obs
    hdu.header['IMAGETYP'] = imagetyp
    hdu.header['EXPTIME'] = 60.0
    hdu.writeto(filename, overwrite=True)

def test_organization():
    base_dir = Path("test_organizer_env")
    source_dir = base_dir / "source" / "2026-02-11" / "LIGHT"
    dest_dir = base_dir / "organized"
    
    if base_dir.exists():
        shutil.rmtree(base_dir)
    
    source_dir.mkdir(parents=True)
    
    # Create mixed files
    # file1: Target A
    create_mock_fits(source_dir / "file_A.fits", "TargetA", "2026-02-11T20:00:00", "Light Frame")
    # file2: Target B
    create_mock_fits(source_dir / "file_B.fits", "TargetB", "2026-02-11T21:00:00", "Light Frame")
    # file3: Target A (Flat) - just to test type
    create_mock_fits(source_dir / "file_A_flat.fits", "TargetA", "2026-02-11T19:00:00", "Flat Field")

    print("Running Organization (Dry Run)...")
    organize_directory(str(source_dir), str(dest_dir), dry_run=True)

    print("\nRunning Organization (Actual)...")
    organize_directory(str(source_dir), str(dest_dir), dry_run=False)
    
    # Verify Structure
    expected_A = dest_dir / "TargetA" / "2026-02-11" / "LIGHT" / "file_A.fits"
    expected_B = dest_dir / "TargetB" / "2026-02-11" / "LIGHT" / "file_B.fits"
    expected_A_Flat = dest_dir / "TargetA" / "2026-02-11" / "FLAT" / "file_A_flat.fits"
    
    if expected_A.exists(): print(f"[PASS] Found {expected_A}")
    else: print(f"[FAIL] Missing {expected_A}")
    
    if expected_B.exists(): print(f"[PASS] Found {expected_B}")
    else: print(f"[FAIL] Missing {expected_B}")

    if expected_A_Flat.exists(): print(f"[PASS] Found {expected_A_Flat}")
    else: print(f"[FAIL] Missing {expected_A_Flat}")

if __name__ == "__main__":
    test_organization()
