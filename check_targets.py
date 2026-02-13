import sqlite3
from pathlib import Path
from src.nebulapilot.db import get_db_connection

def check_targets():
    print("--- NebulaPilot Target Audit ---\n")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. List all Targets defined in 'targets' table
    print("[ Targets Table ] (Goals set)")
    cursor.execute("SELECT name, status FROM targets ORDER BY name")
    targets = cursor.fetchall()
    for t in targets:
        print(f"  - {t['name']} ({t['status']})")
    
    print("\n" + "="*30 + "\n")

    # 2. Group Frames by Target Name (Actual file headers)
    print("[ Frames Table ] (Actual files found)")
    cursor.execute("""
        SELECT target_name, COUNT(*) as count 
        FROM frames 
        GROUP BY target_name 
        ORDER BY target_name
    """)
    frames = cursor.fetchall()
    
    if not frames:
        print("  No frames found in database.")
    else:
        for f in frames:
            t_name = f['target_name']
            count = f['count']
            
            # Check if this frame target exists in the main targets table
            cursor.execute("SELECT 1 FROM targets WHERE name = ?", (t_name,))
            exists = cursor.fetchone()
            
            status_tag = ""
            if not exists:
                status_tag = " [WARNING: Not in Targets Table - Maybe a typo?]"
            
            print(f"  - '{t_name}': {count} frames{status_tag}")

    # 3. Check for suspiciously simple typos (optional logic could go here)
    # For now, just listing them is usually enough to spot "M31" vs "M 31"
    
    conn.close()
    print("\nDONE.")

if __name__ == "__main__":
    check_targets()
