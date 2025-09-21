import csv
import os
import db_manager

# --- Configuration ---
# Define the names of the CSV files to be imported.
WAYPOINTS_CSV = 'waypoints.csv'
RUNS_LIFTS_CSV = 'runs_lifts.csv'
ROUTES_CSV = 'routes.csv'

def clear_all_data():
    """ Wipes all data from the tables to ensure a clean import. """
    print("IMPORT: Clearing all existing data from the database...")
    conn = sqlite3.connect(db_manager.DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM waypoints")
    cursor.execute("DELETE FROM run_lift")
    cursor.execute("DELETE FROM routes")
    cursor.execute("DELETE FROM trip_log")
    conn.commit()
    conn.close()
    print("IMPORT: Database cleared.")

def import_waypoints():
    """ Imports waypoints from a CSV file. """
    print(f"IMPORT: Reading waypoints from {WAYPOINTS_CSV}...")
    try:
        with open(WAYPOINTS_CSV, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                db_manager.add_waypoint(row['name'], float(row['lat']), float(row['lon']), float(row['alt']))
        print(f"IMPORT: Successfully imported waypoints.")
    except FileNotFoundError:
        print(f"ERROR: Could not find {WAYPOINTS_CSV}. Please create it.")
    except Exception as e:
        print(f"ERROR: An error occurred while importing waypoints: {e}")

def import_runs_lifts():
    """ 
    Imports runs and lifts from a CSV file.
    This function looks up waypoint IDs by their names for convenience.
    """
    print(f"IMPORT: Reading runs and lifts from {RUNS_LIFTS_CSV}...")
    # Create a name-to-ID mapping for waypoints
    waypoints = db_manager.get_all_waypoints()
    waypoint_map = {wp['name']: wp['id'] for wp in waypoints}

    try:
        with open(RUNS_LIFTS_CSV, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Convert semicolon-separated names to a list of IDs
                waypoint_names = [name.strip() for name in row['waypoints'].split(';')]
                waypoint_ids = [waypoint_map[name] for name in waypoint_names if name in waypoint_map]
                
                if len(waypoint_ids) == len(waypoint_names):
                    db_manager.add_run_lift(row['name'], waypoint_ids, row['type'], row['difficulty'])
                else:
                    print(f"WARNING: Skipping run '{row['name']}' due to missing waypoint names.")
        print("IMPORT: Successfully imported runs and lifts.")
    except FileNotFoundError:
        print(f"ERROR: Could not find {RUNS_LIFTS_CSV}. Please create it.")
    except Exception as e:
        print(f"ERROR: An error occurred while importing runs/lifts: {e}")

def import_routes():
    """ 
    Imports routes from a CSV file.
    This function looks up run/lift IDs by their names.
    """
    print(f"IMPORT: Reading routes from {ROUTES_CSV}...")
    # Create a name-to-ID mapping for runs/lifts
    runs_lifts = db_manager.get_all_runs_structured()
    run_lift_map = {run['name']: run['id'] for run in runs_lifts}

    try:
        with open(ROUTES_CSV, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Convert semicolon-separated names to a list of IDs
                run_names = [name.strip() for name in row['runs'].split(';')]
                run_ids = [run_lift_map[name] for name in run_names if name in run_lift_map]

                if len(run_ids) == len(run_names):
                    db_manager.add_route(row['name'], run_ids, row['end_area'], row['difficulty'])
                else:
                    print(f"WARNING: Skipping route '{row['name']}' due to missing run/lift names.")
        print("IMPORT: Successfully imported routes.")
    except FileNotFoundError:
        print(f"ERROR: Could not find {ROUTES_CSV}. Please create it.")
    except Exception as e:
        print(f"ERROR: An error occurred while importing routes: {e}")

if __name__ == "__main__":
    print("--- Starting Database Import ---")
    
    # 1. Ensure the database and tables exist
    db_manager.setup_database()
    
    # 2. Clear out any old data for a fresh start
    clear_all_data()
    
    # 3. Import data in order of dependency
    import_waypoints()
    import_runs_lifts()
    import_routes()
    
    print("\n--- Database Import Complete ---")
