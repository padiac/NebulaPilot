import sqlite3
import os
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".nebulapilot" / "nebulapilot.db"

def get_db_connection(db_path=None):
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Targets table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS targets (
        name TEXT PRIMARY KEY,
        goal_l REAL DEFAULT 0,
        goal_r REAL DEFAULT 0,
        goal_g REAL DEFAULT 0,
        goal_b REAL DEFAULT 0,
        status TEXT DEFAULT 'IN_PROGRESS',
        last_wbpp_time TEXT
    )
    """)
    
    # Frames table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS frames (
        path TEXT PRIMARY KEY,
        target_name TEXT,
        filter TEXT,
        exptime_sec REAL,
        date_obs TEXT,
        fwhm REAL,
        eccentricity REAL,
        star_count INTEGER,
        background REAL,
        decision TEXT DEFAULT 'APPROVED',
        score REAL,
        FOREIGN KEY (target_name) REFERENCES targets (name)
    )
    """)
    
    conn.commit()
    conn.close()

def add_target(name, goals=None, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if goals is None:
        goals = (0, 0, 0, 0)
    cursor.execute(
        "INSERT OR IGNORE INTO targets (name, goal_l, goal_r, goal_g, goal_b) VALUES (?, ?, ?, ?, ?)",
        (name, *goals)
    )
    conn.commit()
    conn.close()

def get_targets(db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM targets")
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_target_goals(name, goals, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE targets SET goal_l=?, goal_r=?, goal_g=?, goal_b=? WHERE name=?",
        (*goals, name)
    )
    conn.commit()
    conn.close()

def add_frame(frame_data, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO frames (
            path, target_name, filter, exptime_sec, date_obs, 
            fwhm, eccentricity, star_count, background, decision, score
        ) VALUES (:path, :target_name, :filter, :exptime_sec, :date_obs, 
                  :fwhm, :eccentricity, :star_count, :background, :decision, :score)
    """, frame_data)
    conn.commit()
    conn.close()

def get_target_progress(target_name, db_path=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT filter, SUM(exptime_sec) as total_sec 
        FROM frames 
        WHERE target_name = ? AND decision = 'APPROVED'
        GROUP BY filter
    """, (target_name,))
    rows = cursor.fetchall()
    conn.close()
    
    progress = {"L": 0, "R": 0, "G": 0, "B": 0}
    for row in rows:
        f = row["filter"].upper()
        if f in progress:
            progress[f] = row["total_sec"] / 60.0 # Convert to minutes
    return progress

if __name__ == "__main__":
    init_db()
    print("Database initialized at", DEFAULT_DB_PATH)
