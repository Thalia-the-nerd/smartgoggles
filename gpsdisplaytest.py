import time
import board
import digitalio
import adafruit_ssd1306
import gps
from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
# Display parameters
WIDTH = 128
HEIGHT = 64

# --- Pin Definitions (using board library for portability) ---
# These match the pin numbers from the guide for SPI communication
SPI_CLK = board.SCK  # Physical Pin 23
SPI_MOSI = board.MOSI # Physical Pin 19

# NOTE: We use GPIO 5 for Chip Select because the hardware CE0 (GPIO 8)
# is exclusively controlled by the kernel's SPI driver, causing a conflict.
OLED_CS = board.D5   # Physical Pin 29

OLED_DC = board.D25   # Physical Pin 22
OLED_RST = board.D27  # Physical Pin 13

# --- Initialize SPI and Display ---
try:
    # Initialize the Reset pin
    reset_pin = digitalio.DigitalInOut(OLED_RST)

    # Initialize the SPI interface
    spi = board.SPI()

    # Initialize the display driver
    oled = adafruit_ssd1306.SSD1306_SPI(
        WIDTH,
        HEIGHT,
        spi,
        dc=digitalio.DigitalInOut(OLED_DC),
        reset=reset_pin,
        cs=digitalio.DigitalInOut(OLED_CS),
    )
    print("OLED Initialized Successfully via SPI!")

except (ValueError, RuntimeError) as e:
    print(f"Error initializing display: {e}")
    print("Check your wiring and ensure SPI is enabled in raspi-config.")
    exit()


# --- Main Application Logic ---

# Clear the OLED display initially
oled.fill(0)
oled.show()

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
image = Image.new("1", (oled.width, oled.height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Load a default font.
try:
    font = ImageFont.load_default()
except IOError:
    print("Default font not found, text will not be displayed.")
    font = None

# Connect to the gpsd daemon.
# We don't set the mode here, we'll use the stream method later.
session = gps.gps()

def display_message(message):
    draw.rectangle((0, 0, oled.width, oled.height), outline=0, fill=0)
    if font:
        # Use textbbox to be compatible with Pillow 10+ and fix DeprecationWarning.
        bbox = draw.textbbox((0, 0), message, font=font)
        textwidth = bbox[2] - bbox[0]
        textheight = bbox[3] - bbox[1]
        x = (oled.width - textwidth) // 2
        y = (oled.height - textheight) // 2
        draw.text((x, y), message, font=font, fill=255)
    oled.image(image)
    oled.show()

def get_gps_data():
    # The stream method starts a background thread that polls gpsd automatically.
    session.stream(gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)
    animation_frame = 0

    while True:
        # Directly access the session data which is updated by the background thread.
        # This is non-blocking, so the UI will always update.
        if session.fix.mode >= 2: # Mode 2 = 2D fix, Mode 3 = 3D fix
            latitude = session.fix.latitude
            longitude = session.fix.longitude
            # Check for altitude, as it may not always be present
            altitude = session.fix.altitude if hasattr(session.fix, 'altitude') else 'n/a'

            # Draw a black filled box to clear the image.
            draw.rectangle((0, 0, oled.width, oled.height), outline=0, fill=0)

            # Write GPS data
            if font:
                draw.text((0, 0),  f"Lat: {latitude:.4f}", font=font, fill=255)
                draw.text((0, 16), f"Lon: {longitude:.4f}", font=font, fill=255)
                alt_text = f"Alt: {altitude:.1f}m" if isinstance(altitude, (int, float)) else f"Alt: {altitude}"
                draw.text((0, 32), alt_text, font=font, fill=255)

            # Display image.
            oled.image(image)
            oled.show()
        else:
            # No fix yet, display a waiting message with animation
            dots = "." * (animation_frame % 4)
            display_message(f"Searching{dots}")

        animation_frame += 1
        # Control the refresh rate of the screen
        time.sleep(0.5)

if __name__ == '__main__':
    try:
        get_gps_data()
    except KeyboardInterrupt:
        print("\nExiting script.")
    finally:
        # Ensure the OLED is cleared on exit
        if 'oled' in locals():
            oled.fill(0)
            oled.show()

