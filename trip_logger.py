import threading
import time
import sqlite3
import db_manager  # Assuming db_manager.py is in the same directory

# --- Configuration ---
LOG_INTERVAL_SECONDS = 5  # How often to attempt to write a data point to the log.
MIN_SPEED_MPS = 1.0       # Minimum speed in meters/second to be considered "moving".

def trip_logger_thread(gps_data, data_lock, stop_event):
    """
    This function runs in a separate thread to automatically log trip data.
    It wakes up periodically, checks for a valid GPS fix and sufficient speed,
    and then writes the data to the SQLite database.

    Args:
        gps_data (dict): The shared dictionary to read GPS data from.
        data_lock (threading.Lock): The lock for thread-safe access to gps_data.
        stop_event (threading.Event): An event to signal the thread to stop.
    """
    print("TRIP_LOGGER: Thread started.")
    conn = None
    try:
        # Establish a single database connection for the life of the thread
        conn = sqlite3.connect(db_manager.DB_FILE, check_same_thread=False)
        cursor = conn.cursor()

        # The main loop continues until the stop_event is set
        while not stop_event.is_set():
            # The wait() function will block but returns early if the event is set
            if stop_event.wait(LOG_INTERVAL_SECONDS):
                break  # Exit loop if stop event was set during wait

            lat, lon, alt, speed = None, None, None, None
            log_this_point = False

            # Safely read the required data from the shared dictionary.
            with data_lock:
                # We only log if we have a fix and are moving above a minimum speed.
                # This prevents logging data while standing still (e.g., on a lift).
                if gps_data.get('fix') and gps_data.get('speed', 0) > MIN_SPEED_MPS:
                    lat = gps_data.get('lat')
                    lon = gps_data.get('lon')
                    alt = gps_data.get('alt_m') # Ensure we are using meters
                    speed = gps_data.get('speed')
                    # Check that all data points are valid before logging
                    if all(v is not None for v in [lat, lon, alt, speed]):
                        log_this_point = True

            # Insert the captured data into the database if conditions were met
            if log_this_point:
                try:
                    # The timestamp is automatically added by the database (CURRENT_TIMESTAMP).
                    cursor.execute(
                        "INSERT INTO trip_log (lat, lon, alt, speed) VALUES (?, ?, ?, ?)",
                        (lat, lon, alt, speed)
                    )
                    conn.commit()
                    # print(f"TRIP_LOGGER: Logged point at speed {speed:.2f} m/s") # Uncomment for verbose logging
                except sqlite3.Error as e:
                    print(f"TRIP_LOGGER: Database write error: {e}")

    except sqlite3.Error as e:
        print(f"TRIP_LOGGER: Failed to connect to database: {e}")
    except Exception as e:
        print(f"TRIP_LOGGER: An unexpected error occurred: {e}")
    finally:
        # Ensure the database connection is closed when the thread exits
        if conn:
            conn.close()
            print("TRIP_LOGGER: Database connection closed.")
    
    print("TRIP_LOGGER: Thread stopped.")

