#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import logging
import time
import traceback
import datetime
import gps
from PIL import Image, ImageDraw, ImageFont

# Get the directory where the script is located
script_dir = os.path.dirname(os.path.realpath(__file__))

# Construct paths to the resources relative to the script's location
libdir = os.path.join(script_dir, 'waveshare_OLED')
picdir = os.path.join(script_dir, 'pic')

# Add the lib directory to the system path so Python can find the module
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_OLED import OLED_1in51

logging.basicConfig(level=logging.DEBUG)

try:
    # Initialize the OLED display
    disp = OLED_1in51.OLED_1in51()
    disp.Init()
    disp.clear()

    # Create image and font objects
    image = Image.new('1', (disp.width, disp.height), "WHITE")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 12)

    # Initialize a GPS session
    session = gps.gps(mode=gps.WATCH_ENABLE)

    # GPS data variables
    latitude = "Lat: No Fix"
    longitude = "Lon: No Fix"

    logging.info("Starting GPS session...")

    while True:
        # Get next update from the GPS session
        report = session.next()

        # Check if the report has a valid fix
        if report['class'] == 'TPV':
            if getattr(report, 'mode', 0) >= 2:
                latitude = f"Lat: {report.lat:.4f}°"
                longitude = f"Lon: {report.lon:.4f}°"
                logging.info(f"Updated GPS Data: {latitude}, {longitude}")
            else:
                latitude = "Lat: No Fix"
                longitude = "Lon: No Fix"
                logging.info("GPS: No fix available.")

        # Clear the image buffer
        draw.rectangle([(0,0), (disp.width, disp.height)], fill=1)

        # Get and format current time
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")

        # Draw the text on the image
        draw.text((5, 5), f"Time: {current_time}", font=font, fill=0)
        draw.text((5, 25), latitude, font=font, fill=0)
        draw.text((5, 45), longitude, font=font, fill=0)

        # Show the image on the OLED display
        disp.ShowImage(disp.getbuffer(image.rotate(180)))
        time.sleep(1)

except IOError as e:
    logging.info(e)
except KeyboardInterrupt:
    logging.info("ctrl + c:")
    disp.module_exit()
    sys.exit()
except gps.ConnectionRefusedError:
    logging.error("Could not connect to gpsd. Make sure the service is running.")
    sys.exit(1)
except Exception as e:
    logging.info(f"An unexpected error occurred: {e}")
