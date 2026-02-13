import sqlite3
import os
from pathlib import Path
from astropy.io import fits
from src.nebulapilot.db import get_db_connection, add_target

# --- CONFIGURATION: DEFINE YOUR CORRECTIONS HERE ---
# Format: "Incorrect Name found in file": "Correct Name you want"
CORRECTIONS = {
    # Examples (Enable/Edit these):
    # "M 42": "M42",
    # "Andromeda": "M31",
    # "Horsehead": "IC434",
}

def fix_targets():
    print("--- NebulaPilot Target Fixer ---\n")
    
    if not CORRECTIONS:
        print("No corrections defined in 'CORRECTIONS' dictionary.")
        print("Please edit this script and add your fixes first.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    for bad_name, good_name in CORRECTIONS.items():
        print(f"\nProcessing '{bad_name}' -> '{good_name}'...")
        
        # 1. Find frames with the bad target name
        cursor.execute("SELECT path FROM frames WHERE target_name = ?", (bad_name,))
        rows = cursor.fetchall()
        
        if not rows:
            print(f"  No frames found for '{bad_name}'. Skipping.")
            continue
            
        print(f"  Found {len(rows)} frames to fix.")
        
        # Ensure the destination target exists in the DB
        # (If it doesn't, add it with default goals so FK constraint is satisfied)
        cursor.execute("SELECT 1 FROM targets WHERE name = ?", (good_name,))
        if not cursor.fetchone():
            print(f"  Target '{good_name}' not in DB. Creating it...")
            add_target(good_name, db_path=None) # Uses default connection logic

        success_count = 0
        fail_count = 0
        
        for row in rows:
            file_path = row['path']
            try:
                # A. Update FITS Header
                with fits.open(file_path, mode='update') as hdul:
                    if 'OBJECT' in hdul[0].header:
                        old_val = hdul[0].header['OBJECT']
                        hdul[0].header['OBJECT'] = good_name
                        hdul.flush() # Save changes
                        # print(f"    Fixed header: {Path(file_path).name} ({old_val} -> {good_name})")
                    else:
                        print(f"    WARNING: No OBJECT keyword in {Path(file_path).name}")
                
                # B. Update Database Record
                cursor.execute(
                    "UPDATE frames SET target_name = ? WHERE path = ?", 
                    (good_name, file_path)
                )
                success_count += 1
                
            except Exception as e:
                print(f"    ERROR fixing {file_path}: {e}")
                fail_count += 1

        # C. Cleanup Old Target (if empty)
        cursor.execute("SELECT COUNT(*) FROM frames WHERE target_name = ?", (bad_name,))
        remaining = cursor.fetchone()[0]
        if remaining == 0:
            print(f"  Target '{bad_name}' has no more frames. Deleting from targets table...")
            cursor.execute("DELETE FROM targets WHERE name = ?", (bad_name,))
        
        conn.commit()
        print(f"  Done. Fixed: {success_count}, Failed: {fail_count}")

    conn.close()
    print("\n--- All Corrections Completed ---")
    print("Please run 'check_targets.py' or restart NebulaPilot to verify.")

if __name__ == "__main__":
    fix_targets()
