import time
import board
import digitalio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont

# --- Pin Definitions ---
# This setup uses the default hardware SPI pins.
WIDTH = 128
HEIGHT = 64
SPI_CLK = board.SCK
SPI_MOSI = board.MOSI
OLED_CS = board.D8   # Default hardware SPI Chip Select (CE0) on Physical Pin 24
OLED_DC = board.D25
OLED_RST = board.D27

# --- Initialize Display ---
try:
    reset_pin = digitalio.DigitalInOut(OLED_RST)
    spi = board.SPI()
    oled = adafruit_ssd1306.SSD1306_SPI(
        WIDTH,
        HEIGHT,
        spi,
        dc=digitalio.DigitalInOut(OLED_DC),
        reset=reset_pin,
        cs=digitalio.DigitalInOut(OLED_CS),
    )
    print("OLED Initialized Successfully!")

    # --- Create a test message ---
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    # Draw a black filled box to clear the image.
    draw.rectangle((0, 0, oled.width, oled.height), outline=0, fill=0)

    # Center the text
    message = "Hello World!"
    bbox = draw.textbbox((0, 0), message, font=font)
    textwidth = bbox[2] - bbox[0]
    textheight = bbox[3] - bbox[1]
    x = (oled.width - textwidth) // 2
    y = (oled.height - textheight) // 2
    draw.text((x, y), message, font=font, fill=255)

    # Display the image
    oled.image(image)
    oled.show()
    print("'Hello World' should be displayed on the screen.")

# This except block is required to match the 'try' at the beginning.
except (ValueError, RuntimeError) as e:
    print(f"Error initializing display: {e}")

