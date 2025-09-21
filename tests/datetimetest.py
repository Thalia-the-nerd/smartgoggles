#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import logging
import time
import traceback
import datetime
import smbus

# Get the directory where the script is located
script_dir = os.path.dirname(os.path.realpath(__file__))

# Construct paths to the resources relative to the script's location
libdir = os.path.join(script_dir, 'waveshare_OLED')
picdir = os.path.join(script_dir, 'pic')

# Add the lib directory to the system path so Python can find the module
if os.path.exists(libdir):
    sys.path.append(libdir)

from waveshare_OLED import OLED_1in51
from PIL import Image,ImageDraw,ImageFont

logging.basicConfig(level=logging.DEBUG)

try:
    disp = OLED_1in51.OLED_1in51()

    logging.info("\r1.51inch OLED ")
    # Initialize library.
    disp.Init()
    # Clear display.
    logging.info("clear display")
    disp.clear()

    # Create blank image for drawing.
    image = Image.new('1', (disp.width, disp.height), "WHITE")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 14)

    while True:
        # Clear the image buffer for new text
        draw.rectangle([(0,0), (disp.width, disp.height)], fill=1)

        # Get current date and time
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")
        current_date = now.strftime("%Y-%m-%d")

        # Draw the text on the image
        draw.text((5, 5), current_date, font=font, fill=0)
        draw.text((5, 25), current_time, font=font, fill=0)

        # Show the image on the OLED display
        disp.ShowImage(disp.getbuffer(image.rotate(180)))
        time.sleep(1)

except IOError as e:
    logging.info(e)
except KeyboardInterrupt:
    logging.info("ctrl + c:")
    disp.module_exit()
    sys.exit()
