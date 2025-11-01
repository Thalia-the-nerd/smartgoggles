import sqlite3
import os
from datetime import date

# --- Configuration ---
DB_FILE = 'skidata.db'
LOG_DIRECTORY = 'daily_logs'

# --- Helper Functions ---
def execute_query(db_path, query, params=(), fetchone=False, fetchall=False, commit=False):
    """A centralized function to execute database queries against a specific DB file."""
    if 'daily_logs' in db_path and not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path))
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
    # (Setup queries remain the same)
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

# (Functions like add_waypoint, add_run_lift etc. remain unchanged)
def add_waypoint(name, lat, lon, alt, waypoint_type='junction'):
    execute_query(DB_FILE, "INSERT INTO waypoints (name, lat, lon, alt, type) VALUES (?, ?, ?, ?, ?)", (name, lat, lon, alt, waypoint_type), commit=True)
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
def delete_route(route_id):
    execute_query(DB_FILE, "DELETE FROM routes WHERE id = ?", (route_id,), commit=True)
def update_waypoint(wp_id, name, lat, lon, alt):
    execute_query(DB_FILE, "UPDATE waypoints SET name=?, lat=?, lon=?, alt=? WHERE id=?", (name, lat, lon, alt, wp_id), commit=True)

# --- Data Retrieval for Navigation ---
def get_all_waypoints():
    rows = execute_query(DB_FILE, "SELECT * FROM waypoints ORDER BY name", fetchall=True)
    return [dict(row) for row in rows]

def get_waypoint_by_id(wp_id):
    """Retrieves a single waypoint by its primary key ID."""
    row = execute_query(DB_FILE, "SELECT * FROM waypoints WHERE id = ?", (wp_id,), fetchone=True)
    return dict(row) if row else None

def get_all_runs_structured():
    rows = execute_query(DB_FILE, "SELECT * FROM run_lift ORDER BY name", fetchall=True)
    runs = []
    for row in rows:
        run_dict = dict(row)
        run_dict['waypoints_list'] = [int(wp_id) for wp_id in run_dict['waypoints'].split(',') if wp_id]
        runs.append(run_dict)
    return runs

def get_all_routes_structured():
    """Retrieves all routes and parses their run lists."""
    rows = execute_query(DB_FILE, "SELECT * FROM routes ORDER BY name", fetchall=True)
    routes = []
    for row in rows:
        route_dict = dict(row)
        route_dict['runs_list'] = [int(run_id) for run_id in route_dict['runs'].split(',') if run_id]
        routes.append(route_dict)
    return routes

def get_routes_starting_at(start_wp_id):
    """
    Finds all predefined routes that start at a given waypoint ID.
    This is complex because it has to trace the first run of each route.
    """
    all_routes = get_all_routes_structured()
    all_runs = get_all_runs_structured()
    runs_by_id = {run['id']: run for run in all_runs}
    
    starting_routes = []
    for route in all_routes:
        if not route.get('runs_list'):
            continue
        
        first_run_id = route['runs_list'][0]
        first_run = runs_by_id.get(first_run_id)
        
        if not first_run or not first_run.get('waypoints_list'):
            continue
            
        first_waypoint_id = first_run['waypoints_list'][0]
        
        if first_waypoint_id == start_wp_id:
            starting_routes.append(route)
            
    return starting_routes

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

# (Personal best and daily log functions remain unchanged)
def get_personal_best(run_id):
    result = execute_query(DB_FILE, "SELECT best_time_seconds FROM personal_bests WHERE run_id = ?", (run_id,), fetchone=True)
    return result['best_time_seconds'] if result else None
def update_personal_best(run_id, new_time):
    execute_query(DB_FILE, "INSERT OR REPLACE INTO personal_bests (run_id, best_time_seconds) VALUES (?, ?)", (run_id, new_time), commit=True)
def get_daily_db_path():
    today_str = date.today().strftime('%Y-%m-%d')
    return os.path.join(LOG_DIRECTORY, f"{today_str}.db")
def log_completed_run(analytics_data):
    db_path = get_daily_db_path()
    execute_query(db_path, '''CREATE TABLE IF NOT EXISTS run_log (id INTEGER PRIMARY KEY, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, run_name TEXT, duration_seconds REAL, vertical_m REAL, top_speed_kph REAL)''')
    query = "INSERT INTO run_log (run_name, duration_seconds, vertical_m, top_speed_kph) VALUES (?, ?, ?, ?)"
    params = (analytics_data['run_name'], analytics_data['duration_seconds'], analytics_data['vertical_m'], analytics_data['top_speed_kph'])
    execute_query(db_path, query, params, commit=True)
def get_days_bests():
    db_path = get_daily_db_path()
    if not os.path.exists(db_path): return {'longest_run': None, 'biggest_drop': None, 'fastest_run': None}
    execute_query(db_path, '''CREATE TABLE IF NOT EXISTS run_log (id INTEGER, timestamp DATETIME, run_name TEXT, duration_seconds REAL, vertical_m REAL, top_speed_kph REAL)''')
    longest_run = execute_query(db_path, "SELECT * FROM run_log ORDER BY duration_seconds DESC LIMIT 1", fetchone=True)
    biggest_drop = execute_query(db_path, "SELECT * FROM run_log WHERE vertical_m > 0 ORDER BY vertical_m DESC LIMIT 1", fetchone=True)
    fastest_run = execute_query(db_path, "SELECT * FROM run_log ORDER BY top_speed_kph DESC LIMIT 1", fetchone=True)
    return {'longest_run': dict(longest_run) if longest_run else None, 'biggest_drop': dict(biggest_drop) if biggest_drop else None, 'fastest_run': dict(fastest_run) if fastest_run else None}
def get_run_log_entries():
    db_path = get_daily_db_path()
    if not os.path.exists(db_path): return []
    execute_query(db_path, '''CREATE TABLE IF NOT EXISTS run_log (id INTEGER, timestamp DATETIME, run_name TEXT, duration_seconds REAL, vertical_m REAL, top_speed_kph REAL)''')
    rows = execute_query(db_path, "SELECT * FROM run_log ORDER BY timestamp DESC", fetchall=True)
    return [dict(row) for row in rows]
def get_performance_profile_from_log():
    db_path = get_daily_db_path()
    if not os.path.exists(db_path): return {}
    execute_query(db_path, '''CREATE TABLE IF NOT EXISTS trip_log (id INTEGER, lat REAL, lon REAL, alt REAL, speed REAL)''')
    query = "SELECT SUM(CASE WHEN speed < 4.2 THEN 5 ELSE 0 END) AS relaxed_time, SUM(CASE WHEN speed >= 4.2 AND speed < 11.1 THEN 5 ELSE 0 END) AS cruising_time, SUM(CASE WHEN speed >= 11.1 THEN 5 ELSE 0 END) AS aggressive_time FROM trip_log"
    profile = execute_query(db_path, query, fetchone=True)
    return dict(profile) if profile and profile['relaxed_time'] is not None else {}
def get_todays_stats_from_daily_log():
    db_path = get_daily_db_path()
    if not os.path.exists(db_path): return {'total_vertical_m': 0, 'top_speed_kph': 0}
    execute_query(db_path, '''CREATE TABLE IF NOT EXISTS trip_log (id INTEGER, lat REAL, lon REAL, alt REAL, speed REAL)''')
    min_alt, max_alt = execute_query(db_path, "SELECT MIN(alt), MAX(alt) FROM trip_log", fetchone=True) or (0,0)
    total_vertical_m = (max_alt - min_alt) if max_alt is not None and min_alt is not None else 0
    top_speed_mps = (execute_query(db_path, "SELECT MAX(speed) FROM trip_log", fetchone=True) or [0])[0] or 0
    top_speed_kph = top_speed_mps * 3.6
    return {'total_vertical_m': total_vertical_m, 'top_speed_kph': top_speed_kph}


