import sqlite3
import os
import json
from datetime import date, datetime

# --- Configuration ---
DB_FILE = 'skidata.db'
LOG_DIRECTORY = 'daily_logs'
LAST_ROUTE_FILE = '.last_route.json' # Temp file to store last route

# --- Helper Functions ---
def execute_query(db_path, query, params=(), fetchone=False, fetchall=False, commit=False):
    """A centralized function to execute database queries against a specific DB file."""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        if commit: conn.commit()
        result = None
        if fetchone: result = cursor.fetchone()
        elif fetchall: result = cursor.fetchall()
        return result
    except sqlite3.Error as e:
        print(f"DB_MANAGER_ERROR: Failed to execute query on {db_path}. Error: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

# --- Main DB (skidata.db) Functions ---
def setup_database():
    """Sets up the initial database schema for the main, persistent resort data."""
    execute_query(DB_FILE, '''
    CREATE TABLE IF NOT EXISTS waypoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        lat REAL, lon REAL, alt REAL NOT NULL, type TEXT DEFAULT 'junction'
    )''', commit=True)
    execute_query(DB_FILE, '''
    CREATE TABLE IF NOT EXISTS run_lift (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        waypoints TEXT NOT NULL, type TEXT NOT NULL, difficulty TEXT NOT NULL
    )''', commit=True)
    execute_query(DB_FILE, '''
    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        runs TEXT NOT NULL, end_area TEXT, difficulty TEXT
    )''', commit=True)
    execute_query(DB_FILE, '''
    CREATE TABLE IF NOT EXISTS personal_bests (
        run_id INTEGER PRIMARY KEY, best_time_seconds REAL NOT NULL,
        FOREIGN KEY (run_id) REFERENCES run_lift (id)
    )''', commit=True)
    print("DB_MANAGER: Main database setup/verification complete.")

def add_waypoint(name, lat, lon, alt, wp_type='junction'):
    execute_query(DB_FILE, "INSERT INTO waypoints (name, lat, lon, alt, type) VALUES (?, ?, ?, ?, ?)", (name, lat, lon, alt, wp_type), commit=True)
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
def update_waypoint(wp_id, name, lat, lon, alt, wp_type):
    execute_query(DB_FILE, "UPDATE waypoints SET name=?, lat=?, lon=?, alt=?, type=? WHERE id=?", (name, lat, lon, alt, wp_type, wp_id), commit=True)
def get_personal_best(run_id):
    result = execute_query(DB_FILE, "SELECT best_time_seconds FROM personal_bests WHERE run_id = ?", (run_id,), fetchone=True)
    return result['best_time_seconds'] if result else None
def update_personal_best(run_id, new_time):
    execute_query(DB_FILE, "INSERT OR REPLACE INTO personal_bests (run_id, best_time_seconds) VALUES (?, ?)", (run_id, new_time), commit=True)
def get_all_waypoints():
    rows = execute_query(DB_FILE, "SELECT * FROM waypoints ORDER BY name", fetchall=True)
    return [dict(row) for row in rows] if rows else []
def get_all_runs_structured():
    rows = execute_query(DB_FILE, "SELECT * FROM run_lift ORDER BY name", fetchall=True)
    runs = [dict(row) for row in rows] if rows else []
    for run in runs: run['waypoints_list'] = [int(wp_id) for wp_id in run['waypoints'].split(',') if wp_id]
    return runs
def get_all_routes_structured():
    rows = execute_query(DB_FILE, "SELECT * FROM routes ORDER BY name", fetchall=True)
    routes = [dict(row) for row in rows] if rows else []
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
    os.makedirs(LOG_DIRECTORY, exist_ok=True) # Ensure dir exists
    today_str = date.today().strftime('%Y-%m-%d')
    return os.path.join(LOG_DIRECTORY, f"{today_str}.db")

def setup_daily_db(cursor):
    """
    Creates tables in the daily DB.
    This is called by trip_logger when a new DB file is created.
    """
    # Table for raw GPS pings
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trip_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        lat REAL NOT NULL, lon REAL NOT NULL,
        alt REAL NOT NULL, speed REAL NOT NULL
    )''')
    # Table for completed run analytics
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS run_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        run_name TEXT NOT NULL,
        duration_seconds REAL NOT NULL,
        vertical_m REAL NOT NULL,
        top_speed_kph REAL NOT NULL
    )''')

def log_completed_run(analytics):
    """Logs a completed run's analytics to the daily database."""
    db_path = get_daily_db_path()
    query = """
    INSERT INTO run_log (run_name, duration_seconds, vertical_m, top_speed_kph) 
    VALUES (?, ?, ?, ?)
    """
    params = (
        analytics.get('run_name', 'N/A'),
        analytics.get('duration_seconds', 0),
        analytics.get('vertical_m', 0),
        analytics.get('top_speed_kph', 0)
    )
    execute_query(db_path, query, params, commit=True)

def get_run_log_entries():
    """Gets all completed run entries from today's log."""
    db_path = get_daily_db_path()
    if not os.path.exists(db_path): return []
    
    query = "SELECT timestamp, run_name, duration_seconds, vertical_m FROM run_log ORDER BY timestamp DESC"
    rows = execute_query(db_path, query, fetchall=True)
    if not rows: return []
    
    # Format the time for display
    entries = []
    for row in rows:
        entry = dict(row)
        entry['time'] = datetime.fromisoformat(entry['timestamp']).strftime('%H:%M')
        entries.append(entry)
    return entries

def get_days_bests():
    """Calculates the best run stats from today's run_log table."""
    db_path = get_daily_db_path()
    if not os.path.exists(db_path): return {}

    bests = {}
    
    # Longest duration
    q_dur = "SELECT run_name, duration_seconds FROM run_log ORDER BY duration_seconds DESC LIMIT 1"
    res_dur = execute_query(db_path, q_dur, fetchone=True)
    if res_dur: bests['longest_run'] = dict(res_dur)
    
    # Biggest vertical
    q_vert = "SELECT run_name, vertical_m FROM run_log ORDER BY vertical_m DESC LIMIT 1"
    res_vert = execute_query(db_path, q_vert, fetchone=True)
    if res_vert: bests['biggest_vertical'] = dict(res_vert)

    # Fastest run
    q_speed = "SELECT run_name, top_speed_kph FROM run_log ORDER BY top_speed_kph DESC LIMIT 1"
    res_speed = execute_query(db_path, q_speed, fetchone=True)
    if res_speed: bests['fastest_run'] = dict(res_speed)

    return bests

def get_todays_stats_from_daily_log():
    """Calculates summary stats from today's trip_log."""
    db_path = get_daily_db_path()
    if not os.path.exists(db_path): 
        return {'total_vertical_m': 0, 'top_speed_kph': 0}
    
    stats = execute_query(db_path, "SELECT MIN(alt), MAX(alt), MAX(speed) FROM trip_log", fetchone=True)
    if not stats or stats[0] is None:
        return {'total_vertical_m': 0, 'top_speed_kph': 0}

    min_alt, max_alt, top_speed_mps = stats
    total_vertical_m = (max_alt - min_alt) if max_alt is not None and min_alt is not None else 0
    top_speed_kph = (top_speed_mps or 0) * 3.6
    
    return {'total_vertical_m': total_vertical_m, 'top_speed_kph': top_speed_kph}

# --- Last Route Cache Functions ---

def save_last_navigation_route(waypoints):
    """Saves the waypoints of the last navigated route to a temp file."""
    try:
        # We only need to store the IDs
        waypoint_data = [{'id': wp['id'], 'name': wp['name'], 'lat': wp.get('lat'), 'lon': wp.get('lon'), 'alt': wp.get('alt')} for wp in waypoints]
        with open(LAST_ROUTE_FILE, 'w') as f:
            json.dump(waypoint_data, f)
    except Exception as e:
        print(f"DB_MANAGER_ERROR: Failed to save last route: {e}")

def get_last_navigation_route():
    """Retrieves the waypoints from the last navigated route temp file."""
    if not os.path.exists(LAST_ROUTE_FILE):
        return None
    try:
        with open(LAST_ROUTE_FILE, 'r') as f:
            waypoint_data = json.load(f)
        return waypoint_data # Returns list of waypoint dicts
    except Exception as e:
        print(f"DB_MANAGER_ERROR: Failed to load last route: {e}")
        return None

def clear_last_navigation_route():
    """Deletes the last route temp file."""
    if os.path.exists(LAST_ROUTE_FILE):
        os.remove(LAST_ROUTE_FILE)

