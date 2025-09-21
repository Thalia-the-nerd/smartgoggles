# gps_to_terminal.py
# A script to connect to the gpsd daemon and print real-time
# GPS coordinates (latitude and longitude) to the terminal.

# This script assumes that the gpsd service is running and
# that a GPS device is connected and working.

import gps
import os

print("Starting GPS data stream...")
print("Waiting for a valid GPS fix...")

# Connect to the gpsd daemon
# The WATCH_ENABLE flag tells gpsd to start streaming reports
session = gps.gps(mode=gps.WATCH_ENABLE)

try:
    # Loop continuously to get data from gpsd
    # The session.next() call will block until a new report is available
    for report in session:
        # We are only interested in TPV (Time, Position, Velocity) reports
        if report['class'] == 'TPV':
            
            # The mode must be 2D (2) or 3D (3) for a valid fix
            # mode 1 is no fix, so we ignore it and keep waiting
            if report.mode >= 2:
                latitude = report.lat if 'lat' in report else "n/a"
                longitude = report.lon if 'lon' in report else "n/a"
                
                # Print the data to the terminal
                print(f"Latitude: {latitude}")
                print(f"Longitude: {longitude}")
                
except KeyboardInterrupt:
    # Exit cleanly on a KeyboardInterrupt (Ctrl+C)
    print("\nExiting script.")
finally:
    # Always close the gpsd session
    session.close()
