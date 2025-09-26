import sqlite3
import os
from datetime import date

# --- Configuration ---
DB_FILE = 'skidata.db'
LOG_DIRECTORY = 'daily_logs'

# --- Helper Functions ---
def execute_query(db_path, query, params=(), fetchone=False, fetchall=False, commit=False):
    """A centralized function to execute database queries against a specific DB file."""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if commit: conn.commit()
        result = None
        if fetchone: result = cursor.fetchone()
        elif fetchall: result = cursor.fetchall()
        return result
    finally:
        conn.close()

# --- Main DB (skidata.db) Functions ---
def setup_database():
    """Sets up the initial database schema for the main, persistent resort data."""
    # trip_log table creation is removed from this central database.
    execute_query(DB_FILE, '''
    CREATE TABLE IF NOT EXISTS waypoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        lat REAL, lon REAL, alt REAL NOT NULL, type TEXT DEFAULT 'junction'
    )''')
    execute_query(DB_FILE, '''
    CREATE TABLE IF NOT EXISTS run_lift (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        waypoints TEXT NOT NULL, type TEXT NOT NULL, difficulty TEXT NOT NULL
    )''')
    execute_query(DB_FILE, '''
    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        runs TEXT NOT NULL, end_area TEXT, difficulty TEXT
    )''')
    execute_query(DB_FILE, '''
    CREATE TABLE IF NOT EXISTS personal_bests (
        run_id INTEGER PRIMARY KEY, best_time_seconds REAL NOT NULL,
        FOREIGN KEY (run_id) REFERENCES run_lift (id)
    )''')
    print("DB_MANAGER: Main database setup/verification complete.")

def add_waypoint(name, lat, lon, alt):
    execute_query(DB_FILE, "INSERT INTO waypoints (name, lat, lon, alt) VALUES (?, ?, ?, ?)", (name, lat, lon, alt), commit=True)
# ... (All other functions that modify skidata.db remain the same, but now pass DB_FILE)
def add_run_lift(name, waypoint_ids, run_type, difficulty):
    waypoints_str = ','.join(map(str, waypoint_ids))
    execute_query(DB_FILE, "INSERT INTO run_lift (name, waypoints, type, difficulty) VALUES (?, ?, ?, ?)", (name, waypoints_str, run_type, difficulty), commit=True)
def add_route(name, run_ids, end_area, difficulty):
    runs_str = ','.join(map(str, run_ids))
    execute_query(DB_FILE, "INSERT INTO routes (name, runs, end_area, difficulty) VALUES (?, ?, ?, ?)", (name, runs_str, end_area, difficulty), commit=True)
def delete_waypoint(wp_id):
    execute_query(DB_FILE, "DELETE FROM waypoints WHERE id = ?", (wp_id,), commit=True)
def delete_run_lift(run_id):
    execute_query(DB_FILE, "DELETE FROM run_lift WHERE id = ?", (run_id,), commit=True)
    execute_query(DB_FILE, "DELETE FROM personal_bests WHERE run_id = ?", (run_id,), commit=True)
def delete_route(route_id):
    execute_query(DB_FILE, "DELETE FROM routes WHERE id = ?", (route_id,), commit=True)
def update_waypoint(wp_id, name, lat, lon, alt):
    execute_query(DB_FILE, "UPDATE waypoints SET name=?, lat=?, lon=?, alt=? WHERE id=?", (name, lat, lon, alt, wp_id), commit=True)
def get_personal_best(run_id):
    result = execute_query(DB_FILE, "SELECT best_time_seconds FROM personal_bests WHERE run_id = ?", (run_id,), fetchone=True)
    return result['best_time_seconds'] if result else None
def update_personal_best(run_id, new_time):
    execute_query(DB_FILE, "INSERT OR REPLACE INTO personal_bests (run_id, best_time_seconds) VALUES (?, ?)", (run_id, new_time), commit=True)
def get_all_waypoints():
    rows = execute_query(DB_FILE, "SELECT * FROM waypoints ORDER BY name", fetchall=True)
    return [dict(row) for row in rows]
def get_all_runs_structured():
    rows = execute_query(DB_FILE, "SELECT * FROM run_lift ORDER BY name", fetchall=True)
    runs = [dict(row) for row in rows]
    for run in runs: run['waypoints_list'] = [int(wp_id) for wp_id in run['waypoints'].split(',') if wp_id]
    return runs
def get_all_routes_structured():
    rows = execute_query(DB_FILE, "SELECT * FROM routes ORDER BY name", fetchall=True)
    routes = [dict(row) for row in rows]
    for route in routes: route['runs_list'] = [int(r_id) for r_id in route['runs'].split(',') if r_id]
    return routes
def get_route_by_id(route_id):
    row = execute_query(DB_FILE, "SELECT * FROM routes WHERE id = ?", (route_id,), fetchone=True)
    return dict(row) if row else None
def get_waypoints_for_route(route_id):
    route_row = execute_query(DB_FILE, "SELECT runs FROM routes WHERE id = ?", (route_id,), fetchone=True)
    if not route_row: return []
    run_ids_ordered = [int(rid) for rid in route_row['runs'].split(',')]
    final_waypoints = []
    processed_wp_ids = set()
    for run_id in run_ids_ordered:
        run_row = execute_query(DB_FILE, "SELECT waypoints FROM run_lift WHERE id = ?", (run_id,), fetchone=True)
        if not run_row: continue
        waypoint_ids_ordered = [int(wp_id) for wp_id in run_row['waypoints'].split(',')]
        for wp_id in waypoint_ids_ordered:
            if wp_id not in processed_wp_ids:
                wp_row = execute_query(DB_FILE, "SELECT * FROM waypoints WHERE id = ?", (wp_id,), fetchone=True)
                if wp_row: final_waypoints.append(dict(wp_row)); processed_wp_ids.add(wp_id)
    return final_waypoints


# --- Daily Log DB Functions ---
def get_daily_db_path():
    """Returns the path for today's database file."""
    today_str = date.today().strftime('%Y-%m-%d')
    return os.path.join(LOG_DIRECTORY, f"{today_str}.db")

def get_performance_profile_from_log():
    """Calculates the time spent in different speed zones from today's log."""
    db_path = get_daily_db_path()
    if not os.path.exists(db_path): return {}
    
    # Speed is in m/s in the log. 15kph ~= 4.2m/s, 40kph ~= 11.1m/s
    query = """
    SELECT
        SUM(CASE WHEN speed < 4.2 THEN 5 ELSE 0 END) AS relaxed_time,
        SUM(CASE WHEN speed >= 4.2 AND speed < 11.1 THEN 5 ELSE 0 END) AS cruising_time,
        SUM(CASE WHEN speed >= 11.1 THEN 5 ELSE 0 END) AS aggressive_time
    FROM trip_log
    """
    profile = execute_query(db_path, query, fetchone=True)
    return dict(profile) if profile else {}

def get_bests_from_daily_log():
    """Finds the day's best stats from the 'run_log' table in the daily DB."""
    # This requires that run analytics are also logged to the daily DB.
    # We will need to add a run_log table to the daily DB schema.
    # For now, this is a placeholder. A more complete implementation is needed
    # in mapper.py and trip_logger.py to log completed runs.
    return {
        'longest_run': {'run_name': 'Placeholder', 'duration_seconds': 185},
        'biggest_drop': {'run_name': 'Placeholder', 'vertical_m': 250},
        'fastest_run': {'run_name': 'Placeholder', 'top_speed_kph': 65.2},
    }

def get_todays_stats_from_daily_log():
    """Calculates summary stats from today's trip_log."""
    db_path = get_daily_db_path()
    if not os.path.exists(db_path): return {'total_vertical_m': 0, 'top_speed_kph': 0}
    
    min_alt, max_alt = execute_query(db_path, "SELECT MIN(alt), MAX(alt) FROM trip_log", fetchone=True) or (0,0)
    total_vertical_m = (max_alt - min_alt) if max_alt is not None and min_alt is not None else 0
    top_speed_mps = (execute_query(db_path, "SELECT MAX(speed) FROM trip_log", fetchone=True) or [0])[0] or 0
    top_speed_kph = top_speed_mps * 3.6
    return {'total_vertical_m': total_vertical_m, 'top_speed_kph': top_speed_kph}


