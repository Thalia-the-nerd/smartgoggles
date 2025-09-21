# oled_hello_world.py
# A simple script to display "Hello World!" on an SH1106 OLED screen.
# This script is specifically for the Waveshare 1.51" display.
# It uses the modern displayio library.

# Import the necessary libraries
import board
import busio
import displayio
import adafruit_displayio_sh1106
import adafruit_display_text.label
import terminalio
import time

# Release any previous displays
displayio.release_displays()

# Define the OLED screen parameters
WIDTH = 128
HEIGHT = 64

# Create the I2C bus object
i2c = busio.I2C(board.SCL, board.SDA)

# Create the SH1106 display object
display_bus = displayio.I2CDisplay(i2c, device_address=0x3c)
oled = adafruit_displayio_sh1106.SH1106(display_bus, width=WIDTH, height=HEIGHT, rotation=0)

# Create a group to hold the display elements
splash = displayio.Group()

# Create a text label
# You will need to install the adafruit-display-text library:
# pip install adafruit-circuitpython-display-text
text_area = adafruit_display_text.label.Label(terminalio.FONT, text="Hello, world!", color=0xFFFFFF, x=10, y=20)
splash.append(text_area)

# Show the group on the display
oled.show(splash)

# Keep the script running for a few seconds so the message is visible
time.sleep(10)

# Clear the display before exiting
oled.show(None)
