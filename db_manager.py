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
    """Sets up the initial database schema."""
    # Add 'type' column for POI functionality
    try:
        execute_query("ALTER TABLE waypoints ADD COLUMN type TEXT DEFAULT 'junction'")
        print("DB_MANAGER: Added 'type' column to waypoints.")
    except sqlite3.OperationalError:
        pass # Column already exists

    execute_query('''
    CREATE TABLE IF NOT EXISTS waypoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        lat REAL, lon REAL, alt REAL NOT NULL, type TEXT DEFAULT 'junction'
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
    execute_query('''
    CREATE TABLE IF NOT EXISTS personal_bests (
        run_id INTEGER PRIMARY KEY,
        best_time_seconds REAL NOT NULL,
        FOREIGN KEY (run_id) REFERENCES run_lift (id)
    )''')
    # NEW: Table for Run Logbook and Analytics
    execute_query('''
    CREATE TABLE IF NOT EXISTS run_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        run_name TEXT NOT NULL,
        duration_seconds REAL NOT NULL,
        vertical_m REAL NOT NULL,
        top_speed_kph REAL NOT NULL
    )''')
    print("DB_MANAGER: Database setup/verification complete.")

def add_waypoint(name, lat, lon, alt, waypoint_type='junction'):
    execute_query("INSERT INTO waypoints (name, lat, lon, alt, type) VALUES (?, ?, ?, ?, ?)", (name, lat, lon, alt, waypoint_type), commit=True)

def add_run_lift(name, waypoint_ids, run_type, difficulty):
    waypoints_str = ','.join(map(str, waypoint_ids))
    execute_query("INSERT INTO run_lift (name, waypoints, type, difficulty) VALUES (?, ?, ?, ?)", (name, waypoints_str, run_type, difficulty), commit=True)

def add_route(name, run_ids, end_area, difficulty):
    runs_str = ','.join(map(str, run_ids))
    execute_query("INSERT INTO routes (name, runs, end_area, difficulty) VALUES (?, ?, ?, ?)", (name, runs_str, end_area, difficulty), commit=True)

def add_run_log_entry(name, duration, vertical, top_speed):
    """Adds a completed run to the logbook."""
    execute_query(
        "INSERT INTO run_log (run_name, duration_seconds, vertical_m, top_speed_kph) VALUES (?, ?, ?, ?)",
        (name, duration, vertical, top_speed),
        commit=True
    )

# --- Data Deletion & Updates ---
def delete_waypoint(wp_id):
    execute_query("DELETE FROM waypoints WHERE id = ?", (wp_id,), commit=True)

def delete_run_lift(run_id):
    execute_query("DELETE FROM run_lift WHERE id = ?", (run_id,), commit=True)
    execute_query("DELETE FROM personal_bests WHERE run_id = ?", (run_id,), commit=True)

def delete_route(route_id):
    execute_query("DELETE FROM routes WHERE id = ?", (route_id,), commit=True)

def update_waypoint(wp_id, name, lat, lon, alt, waypoint_type='junction'):
    execute_query("UPDATE waypoints SET name=?, lat=?, lon=?, alt=?, type=? WHERE id=?", (name, lat, lon, alt, waypoint_type, wp_id), commit=True)

# --- Personal Bests ---
def get_personal_best(run_id):
    result = execute_query("SELECT best_time_seconds FROM personal_bests WHERE run_id = ?", (run_id,), fetchone=True)
    return result['best_time_seconds'] if result else None

def update_personal_best(run_id, new_time):
    execute_query("INSERT OR REPLACE INTO personal_bests (run_id, best_time_seconds) VALUES (?, ?)", (run_id, new_time), commit=True)

# --- Data Retrieval ---
def get_all_waypoints():
    rows = execute_query("SELECT * FROM waypoints ORDER BY name", fetchall=True)
    return [dict(row) for row in rows]

def get_waypoints_by_type(waypoint_type):
    """Retrieves all waypoints of a specific type (e.g., 'lodge')."""
    rows = execute_query("SELECT * FROM waypoints WHERE type = ? ORDER BY name", (waypoint_type,), fetchall=True)
    return [dict(row) for row in rows] if rows else []

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
                wp_row = execute_query("SELECT * FROM waypoints WHERE id = ?", (wp_id,), fetchone=True)
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

def get_run_log_entries():
    """Retrieves all completed runs for the logbook, newest first."""
    rows = execute_query("SELECT * FROM run_log ORDER BY timestamp DESC", fetchall=True)
    return [dict(row) for row in rows]

def get_days_bests():
    """Retrieves the best achievements from today's run log."""
    longest_run_row = execute_query(
        "SELECT run_name, duration_seconds FROM run_log ORDER BY duration_seconds DESC LIMIT 1",
        fetchone=True
    )
    biggest_vertical_row = execute_query(
        "SELECT run_name, vertical_m FROM run_log ORDER BY vertical_m DESC LIMIT 1",
        fetchone=True
    )
    fastest_run_row = execute_query(
        "SELECT run_name, top_speed_kph FROM run_log ORDER BY top_speed_kph DESC LIMIT 1",
        fetchone=True
    )
    return {
        'longest_run': dict(longest_run_row) if longest_run_row else None,
        'biggest_vertical': dict(biggest_vertical_row) if biggest_vertical_row else None,
        'fastest_run': dict(fastest_run_row) if fastest_run_row else None
    }


