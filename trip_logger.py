import threading
import time
import sqlite3
import os
from datetime import date
import db_manager # Import the db_manager

# --- Configuration ---
LOG_INTERVAL_SECONDS = 5  # How often to attempt to write a data point to the log.
MIN_SPEED_MPS = 1.0       # Minimum speed in meters/second to be considered "moving".
# LOG_DIRECTORY is now managed by db_manager

# --- REMOVED setup_daily_db function ---
# It is now centralized in db_manager.py

def trip_logger_thread(gps_data, data_lock, stop_event):
    """
    This function runs in a separate thread to automatically log trip data
    into a new database file created each day.
    """
    print("TRIP_LOGGER: Thread started.")
    
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
                # --- MODIFICATION: Get path from db_manager ---
                db_path = db_manager.get_daily_db_path()
                
                print(f"TRIP_LOGGER: Connecting to daily database: {db_path}")
                conn = sqlite3.connect(db_path, check_same_thread=False)
                cursor = conn.cursor()
                # --- MODIFICATION: Call db_manager to set up tables ---
                db_manager.setup_daily_db(cursor)
                conn.commit() # Commit the table creation
                print(f"TRIP_LOGGER: Database connection for {current_db_date} is active.")

            # The wait() function will block but returns early if the event is set
            if stop_event.wait(LOG_INTERVAL_SECONDS):
                break  # Exit loop if stop event was set during wait

            lat, lon, alt, speed = None, None, None, None
            log_this_point = False

            with data_lock:
                # Check for fix and minimum speed
                if gps_data.get('fix') and gps_data.get('speed_mps', 0) > MIN_SPEED_MPS:
                    lat, lon = gps_data.get('lat'), gps_data.get('lon')
                    # Use alt_m and speed_mps from gps_handler
                    alt, speed = gps_data.get('alt_m'), gps_data.get('speed_mps') 
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

