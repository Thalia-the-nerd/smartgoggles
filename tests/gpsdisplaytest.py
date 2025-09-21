# gps_display.py
# A script to display GPS data on an OLED screen connected to a Raspberry Pi
# The script connects to the gpsd daemon and displays real-time latitude, longitude, and altitude.

import board
import busio
import time
from digitalio import DigitalInOut, Direction
import adafruit_ssd1306
import gps
import os

# Define the OLED screen parameters
# The user's screen is 128x64 pixels and uses I2C
WIDTH = 128
HEIGHT = 64
i2c = busio.I2C(board.SCL, board.SDA)
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3c)

# Clear the OLED display initially
oled.fill(0)
oled.show()

# Print a message to the console while trying to connect
print("Trying to connect to GPSD...")

# Connect to the gpsd daemon
# The WATCH_ENABLE flag tells gpsd to start streaming reports
session = gps.gps(mode=gps.WATCH_ENABLE)

def display_message(message):
    """
    Clears the OLED and displays a single-line message.
    """
    oled.fill(0)
    oled.text(message, 0, 0, 1)
    oled.show()

def get_gps_data():
    """
    Continuously retrieves and processes GPS data from the gpsd session.
    """
    display_message("Waiting for GPS...")
    
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
                altitude = report.alt if 'alt' in report else "n/a"
                
                # Clear the display before writing new data
                oled.fill(0)
                
                # Display the data on the OLED screen
                # The text() function takes text, x, y, and color
                oled.text("Lat: {:.4f}".format(latitude), 0, 0, 1)
                oled.text("Lon: {:.4f}".format(longitude), 0, 16, 1)
                oled.text("Alt: {}m".format(altitude), 0, 32, 1)
                
                # Show the changes on the display
                oled.show()
            
            # If there is no fix, keep displaying a waiting message
            else:
                display_message("Waiting for GPS...")
                
    
if __name__ == '__main__':
    try:
        get_gps_data()
    except KeyboardInterrupt:
        # Exit cleanly on a KeyboardInterrupt (Ctrl+C)
        print("\nExiting script.")
    finally:
        # Clean up the display and close the gpsd session
        oled.fill(0)
        oled.show()
        session.close()
