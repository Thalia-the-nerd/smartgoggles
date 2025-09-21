import time
import threading
import board
import busio
import adafruit_ssd1306

# Import project modules
import main_app
import gps_handler
import trip_logger
import db_manager

# --- Global Data and Locks ---
# This dictionary will be shared across threads to pass live GPS data
gps_data = {}
data_lock = threading.Lock()

# --- Main Execution ---
if __name__ == "__main__":
    print("BOOT: System starting...")

    # --- Hardware Initialization ---
    print("BOOT: Initializing display...")
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3c)
        oled.fill(0)
        oled.show()
        print("BOOT: Display initialized successfully.")
    except Exception as e:
        print(f"FATAL: Could not initialize display. {e}")
        exit()

    # --- Database Initialization ---
    print("BOOT: Checking for database...")
    db_manager.create_database() # This will create the DB and tables if they don't exist
    print("BOOT: Database is ready.")

    # --- Start Background Threads ---
    print("BOOT: Starting background threads...")
    
    # GPS Poller Thread
    gps_thread = threading.Thread(
        target=gps_handler.gps_poller, 
        args=(gps_data, data_lock), 
        daemon=True
    )
    gps_thread.start()
    print("BOOT: GPS handler thread started.")

    # Trip Logger Thread
    logger_thread = threading.Thread(
        target=trip_logger.log_trip,
        args=(gps_data, data_lock),
        daemon=True
    )
    logger_thread.start()
    print("BOOT: Trip logger thread started.")

    # --- Launch Main Application ---
    print("BOOT: Handing control to main application...")
    try:
        # This is the blocking call that runs the main UI loop
        main_app.main(oled, gps_data, data_lock)
    except KeyboardInterrupt:
        print("\nBOOT: Shutdown signal received (Ctrl+C).")
    except Exception as e:
        print(f"FATAL: An error occurred in the main application: {e}")
    finally:
        # --- Cleanup ---
        print("BOOT: Cleaning up and shutting down.")
        oled.fill(0)
        oled.show()

