import os
import sys
import threading
import time
import queue

# Add the local library path for the Waveshare driver
sys.path.append(os.path.join(os.path.dirname(__file__), 'waveshare_OLED'))
from waveshare_OLED import OLED_1in51

# Import project modules
import db_manager
import gps_handler
import trip_logger
import main_app
import weather_handler
from ui_manager import UIManager # Import UIManager to use the splash screen

# --- Shared Data, Lock, and Queue ---
gps_queue = queue.Queue()
gps_data = {}
data_lock = threading.Lock()
# Create a list to hold all stop events for clean shutdown
stop_events = []

if __name__ == '__main__':
    print("BOOT: System starting...")
    disp = None
    try:
        # --- Hardware Initialization ---
        print("BOOT: Initializing Waveshare display...")
        disp = OLED_1in51.OLED_1in51()
        disp.Init()
        disp.clear()
        print("BOOT: Display initialized successfully.")

        # --- NEW: Show Splash Screen ---
        ui = UIManager(disp)
        ui.display_splash_screen()

        # --- Database Initialization ---
        print("BOOT: Checking for database...")
        if not os.path.exists('skidata.db'):
            print("BOOT: Database not found. Creating a new one...")
            db_manager.setup_database()
            print("BOOT: Database created.")

        # --- Start Background Threads ---
        print("BOOT: Starting background threads...")
        
        # GPS Poller Thread
        gps_thread = threading.Thread(target=gps_handler.gps_poller, args=(gps_queue,), daemon=True)
        gps_thread.start()
        
        # Trip Logger Thread
        trip_logger_stop_event = threading.Event()
        stop_events.append(trip_logger_stop_event)
        logger_thread = threading.Thread(target=trip_logger.trip_logger_thread, args=(gps_data, data_lock, trip_logger_stop_event), daemon=True)
        logger_thread.start()
        
        # Weather Handler Thread
        weather_thread, weather_stop_event = weather_handler.start_weather_thread()
        stop_events.append(weather_stop_event)
        
        print("BOOT: Threads started.")

        # --- Hand off to Main Application ---
        print("BOOT: Starting main application...")
        # Pass the already-initialized UI manager to the main app
        main_app.main(disp, gps_queue, gps_data, data_lock, ui)

    except IOError as e:
        print(f"FATAL: Could not initialize display. Check wiring. Error: {e}")
    except KeyboardInterrupt:
        print("\nBOOT: Shutdown signal received.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        # --- Cleanup ---
        print("BOOT: Signaling all threads to stop...")
        for event in stop_events:
            event.set()
        
        if disp:
            print("BOOT: Cleaning up display...")
            disp.module_exit()
        print("BOOT: System shut down.")

