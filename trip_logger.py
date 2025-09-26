import threading
import time
import sqlite3
import os
from datetime import date

# --- Configuration ---
LOG_INTERVAL_SECONDS = 5  # How often to attempt to write a data point to the log.
MIN_SPEED_MPS = 1.0       # Minimum speed in meters/second to be considered "moving".
LOG_DIRECTORY = 'daily_logs' # Directory to store the daily database files.

def setup_daily_db(cursor):
    """Creates the necessary table in a new daily database file."""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trip_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        alt REAL NOT NULL,
        speed REAL NOT NULL
    )''')

def trip_logger_thread(gps_data, data_lock, stop_event):
    """
    This function runs in a separate thread to automatically log trip data
    into a new database file created each day.
    """
    print("TRIP_LOGGER: Thread started.")
    
    # Ensure the log directory exists
    os.makedirs(LOG_DIRECTORY, exist_ok=True)
    
    conn = None
    cursor = None
    current_db_date = None

    try:
        while not stop_event.is_set():
            today = date.today()
            # --- Check if the date has changed or if it's the first run ---
            if today != current_db_date:
                if conn:
                    conn.close()
                    print(f"TRIP_LOGGER: Closed DB for {current_db_date}. New day detected.")

                current_db_date = today
                db_filename = f"{current_db_date.strftime('%Y-%m-%d')}.db"
                db_path = os.path.join(LOG_DIRECTORY, db_filename)
                
                print(f"TRIP_LOGGER: Connecting to daily database: {db_path}")
                conn = sqlite3.connect(db_path, check_same_thread=False)
                cursor = conn.cursor()
                setup_daily_db(cursor)
                print(f"TRIP_LOGGER: Database connection for {current_db_date} is active.")

            # The wait() function will block but returns early if the event is set
            if stop_event.wait(LOG_INTERVAL_SECONDS):
                break  # Exit loop if stop event was set during wait

            lat, lon, alt, speed = None, None, None, None
            log_this_point = False

            with data_lock:
                if gps_data.get('fix') and gps_data.get('speed', 0) > MIN_SPEED_MPS:
                    lat, lon = gps_data.get('lat'), gps_data.get('lon')
                    alt, speed = gps_data.get('alt_m'), gps_data.get('speed')
                    if all(v is not None for v in [lat, lon, alt, speed]):
                        log_this_point = True

            if log_this_point and cursor:
                try:
                    cursor.execute(
                        "INSERT INTO trip_log (lat, lon, alt, speed) VALUES (?, ?, ?, ?)",
                        (lat, lon, alt, speed)
                    )
                    conn.commit()
                except sqlite3.Error as e:
                    print(f"TRIP_LOGGER: Database write error: {e}")

    except Exception as e:
        print(f"TRIP_LOGGER: An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("TRIP_LOGGER: Final database connection closed.")
    
    print("TRIP_LOGGER: Thread stopped.")

