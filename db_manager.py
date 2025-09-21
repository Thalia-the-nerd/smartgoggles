import sqlite3
import os

# --- Configuration ---
DB_FILE = 'skidata.db'

# --- Helper Function for DB Interaction ---
def execute_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    """
    A centralized function to execute database queries with a timeout.
    """
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(query, params)
        if commit:
            conn.commit()
        
        result = None
        if fetchone:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()
            
        return result
    finally:
        conn.close()

# --- Setup and Data Addition ---

def setup_database():
    """Sets up the initial database schema, including the new personal_bests table."""
    execute_query('''
    CREATE TABLE IF NOT EXISTS waypoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        lat REAL, lon REAL, alt REAL NOT NULL
    )''')
    execute_query('''
    CREATE TABLE IF NOT EXISTS run_lift (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        waypoints TEXT NOT NULL, type TEXT NOT NULL, difficulty TEXT NOT NULL
    )''')
    execute_query('''
    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        runs TEXT NOT NULL, end_area TEXT, difficulty TEXT
    )''')
    execute_query('''
    CREATE TABLE IF NOT EXISTS trip_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        lat REAL NOT NULL, lon REAL NOT NULL, alt REAL NOT NULL, speed REAL NOT NULL
    )''')
    # NEW: Table to store personal best times for each run/lift.
    execute_query('''
    CREATE TABLE IF NOT EXISTS personal_bests (
        run_id INTEGER PRIMARY KEY,
        best_time_seconds REAL NOT NULL,
        FOREIGN KEY (run_id) REFERENCES run_lift (id)
    )''')
    print("DB_MANAGER: Database setup/verification complete.")

def add_waypoint(name, lat, lon, alt):
    execute_query("INSERT INTO waypoints (name, lat, lon, alt) VALUES (?, ?, ?, ?)", (name, lat, lon, alt), commit=True)

def add_run_lift(name, waypoint_ids, run_type, difficulty):
    waypoints_str = ','.join(map(str, waypoint_ids))
    execute_query("INSERT INTO run_lift (name, waypoints, type, difficulty) VALUES (?, ?, ?, ?)", (name, waypoints_str, run_type, difficulty), commit=True)

def add_route(name, run_ids, end_area, difficulty):
    runs_str = ','.join(map(str, run_ids))
    execute_query("INSERT INTO routes (name, runs, end_area, difficulty) VALUES (?, ?, ?, ?)", (name, runs_str, end_area, difficulty), commit=True)

# --- Data Deletion & Updates ---
def delete_waypoint(wp_id):
    execute_query("DELETE FROM waypoints WHERE id = ?", (wp_id,), commit=True)

def delete_run_lift(run_id):
    execute_query("DELETE FROM run_lift WHERE id = ?", (run_id,), commit=True)
    execute_query("DELETE FROM personal_bests WHERE run_id = ?", (run_id,), commit=True) # Also delete best time

def delete_route(route_id):
    execute_query("DELETE FROM routes WHERE id = ?", (route_id,), commit=True)

def update_waypoint(wp_id, name, lat, lon, alt):
    execute_query("UPDATE waypoints SET name=?, lat=?, lon=?, alt=? WHERE id=?", (name, lat, lon, alt, wp_id), commit=True)

# --- NEW: Functions for Personal Bests ---
def get_personal_best(run_id):
    """Retrieves the personal best time for a given run ID."""
    result = execute_query("SELECT best_time_seconds FROM personal_bests WHERE run_id = ?", (run_id,), fetchone=True)
    return result['best_time_seconds'] if result else None

def update_personal_best(run_id, new_time):
    """Updates or inserts a new personal best time for a run."""
    # "INSERT OR REPLACE" is a convenient SQLite command for this.
    execute_query("INSERT OR REPLACE INTO personal_bests (run_id, best_time_seconds) VALUES (?, ?)", (run_id, new_time), commit=True)

# --- Data Retrieval ---
def get_all_waypoints():
    rows = execute_query("SELECT * FROM waypoints ORDER BY name", fetchall=True)
    return [dict(row) for row in rows]

def get_all_runs_structured():
    rows = execute_query("SELECT * FROM run_lift ORDER BY name", fetchall=True)
    runs = []
    for row in rows:
        run_dict = dict(row)
        run_dict['waypoints_list'] = [int(wp_id) for wp_id in run_dict['waypoints'].split(',') if wp_id]
        runs.append(run_dict)
    return runs

def get_all_routes_structured():
    rows = execute_query("SELECT * FROM routes ORDER BY name", fetchall=True)
    routes = []
    for row in rows:
        route_dict = dict(row)
        route_dict['runs_list'] = [int(r_id) for r_id in route_dict['runs'].split(',') if r_id]
        routes.append(route_dict)
    return routes

def get_route_by_id(route_id):
    row = execute_query("SELECT * FROM routes WHERE id = ?", (route_id,), fetchone=True)
    return dict(row) if row else None

def get_routes_by_filter(end_area, difficulty):
    rows = execute_query("SELECT id, name FROM routes WHERE end_area = ? AND difficulty = ?", (end_area, difficulty), fetchall=True)
    return [dict(row) for row in rows]

def get_waypoints_for_route(route_id):
    route_row = execute_query("SELECT runs FROM routes WHERE id = ?", (route_id,), fetchone=True)
    if not route_row: return []
    run_ids_ordered = [int(rid) for rid in route_row['runs'].split(',')]
    
    final_waypoints = []
    processed_wp_ids = set()
    for run_id in run_ids_ordered:
        run_row = execute_query("SELECT waypoints FROM run_lift WHERE id = ?", (run_id,), fetchone=True)
        if not run_row: continue
        waypoint_ids_ordered = [int(wp_id) for wp_id in run_row['waypoints'].split(',')]
        for wp_id in waypoint_ids_ordered:
            if wp_id not in processed_wp_ids:
                wp_row = execute_query("SELECT name, lat, lon, alt FROM waypoints WHERE id = ?", (wp_id,), fetchone=True)
                if wp_row:
                    final_waypoints.append(dict(wp_row))
                    processed_wp_ids.add(wp_id)
    return final_waypoints


def get_trip_summary():
    min_alt, max_alt = execute_query("SELECT MIN(alt), MAX(alt) FROM trip_log", fetchone=True) or (0,0)
    total_vertical_m = (max_alt - min_alt) if max_alt is not None and min_alt is not None else 0
    top_speed_mps = (execute_query("SELECT MAX(speed) FROM trip_log", fetchone=True) or [0])[0] or 0
    top_speed_kph = top_speed_mps * 3.6
    return {'total_vertical_m': total_vertical_m, 'top_speed_kph': top_speed_kph}

