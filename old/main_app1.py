import os
import time
from PIL import Image, ImageDraw, ImageFont

# Get the absolute path for the font file to ensure it's found
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, 'VCR_OSD_MONO.ttf')

class UIManager:
    """Handles all drawing operations for the Waveshare OLED display."""

    def __init__(self, disp):
        """
        Initializes the UIManager.
        Args:
            disp: The initialized Waveshare display object.
        """
        self.disp = disp
        # Load fonts of different sizes for the UI
        try:
            self.font_small = ImageFont.truetype(FONT_PATH, 12)
            self.font_medium = ImageFont.truetype(FONT_PATH, 16)
            self.font_large = ImageFont.truetype(FONT_PATH, 24)
        except IOError:
            print(f"ERROR: Font file not found at {FONT_PATH}. Using default font.")
            self.font_small = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_large = ImageFont.load_default()

    def _create_image(self):
        """Creates a new blank, white image for drawing in the correct mode."""
        return Image.new('1', (self.disp.width, self.disp.height), "WHITE")

    def _display_image(self, image):
        """Sends the drawn image to the OLED screen's buffer."""
        self.disp.ShowImage(self.disp.getbuffer(image))

    def display_home_screen(self, speed, altitude, gps_fix, current_time):
        """Renders the main dashboard screen."""
        image = self._create_image()
        draw = ImageDraw.Draw(image)

        # GPS Status (Top Left)
        gps_status_text = "GPS: OK" if gps_fix else "GPS: NO FIX"
        draw.text((2, 0), gps_status_text, font=self.font_small, fill=0)

        # Time (Top Right)
        time_width = draw.textlength(current_time, font=self.font_small)
        draw.text((self.disp.width - time_width - 2, 0), current_time, font=self.font_small, fill=0)

        # Speed (Center)
        speed_text = f"{speed:.1f} MPH" if isinstance(speed, (int, float)) else "--- MPH"
        draw.text((5, 18), speed_text, font=self.font_large, fill=0)

        # Altitude (Bottom)
        alt_text = f"{int(altitude)} FT" if isinstance(altitude, (int, float)) else "---- FT"
        draw.text((5, 45), alt_text, font=self.font_medium, fill=0)

        self._display_image(image)

    def display_navigation_screen(self, next_waypoint_info):
        """Renders the navigation screen with route information."""
        image = self._create_image()
        draw = ImageDraw.Draw(image)

        draw.text((2, 0), "NAVIGATION", font=self.font_medium, fill=0)
        draw.line([(0, 20), (self.disp.width, 20)], fill=0, width=1)

        if next_waypoint_info:
            name = next_waypoint_info['name']
            dist = next_waypoint_info['dist_ft']
            # Truncate long names to fit the screen
            draw.text((5, 25), name[:18], font=self.font_medium, fill=0)
            draw.text((5, 45), f"{int(dist)} FT", font=self.font_medium, fill=0)
        else:
            draw.text((5, 30), "No Route", font=self.font_medium, fill=0)
            draw.text((5, 48), "Selected", font=self.font_medium, fill=0)

        self._display_image(image)

    def display_summary_screen(self, summary_data):
        """Renders the trip summary statistics screen."""
        image = self._create_image()
        draw = ImageDraw.Draw(image)

        draw.text((2, 0), "TRIP SUMMARY", font=self.font_medium, fill=0)
        draw.line([(0, 20), (self.disp.width, 20)], fill=0, width=1)

        vert_ft = summary_data.get('vert_ft', 0)
        top_speed = summary_data.get('top_speed', 0)

        draw.text((5, 22), f"Vert: {int(vert_ft)} FT", font=self.font_small, fill=0)
        draw.text((5, 36), f"Top Speed: {top_speed:.1f} MPH", font=self.font_small, fill=0)
        draw.text((5, 50), f"Runs: {summary_data.get('runs', 0)}", font=self.font_small, fill=0)

        self._display_image(image)

    def display_menu(self, title, menu_items, selected_index):
        """Renders a generic, scrollable menu."""
        image = self._create_image()
        draw = ImageDraw.Draw(image)

        draw.text((2, 0), title.upper(), font=self.font_medium, fill=0)
        draw.line([(0, 20), (self.disp.width, 20)], fill=0, width=1)

        y = 22
        # Logic to make the menu view scroll with the selection
        display_start_index = max(0, selected_index - 2)

        for i in range(display_start_index, min(len(menu_items), display_start_index + 3)):
            item = menu_items[i]
            prefix = "> " if i == selected_index else "  "
            draw.text((0, y), f"{prefix}{item['name'][:18]}", font=self.font_small, fill=0)
            y += 14

        self._display_image(image)

    def display_message(self, message, duration_ms=1500):
        """Displays a temporary message, like a notification."""
        image = self._create_image()
        draw = ImageDraw.Draw(image)

        # Center the message on the screen
        text_width = draw.textlength(message, font=self.font_medium)
        x = (self.disp.width - text_width) / 2
        y = (self.disp.height - 16) / 2 # 16 is font height guess
        draw.text((x, y), message, font=self.font_medium, fill=0)

        self._display_image(image)
        time.sleep(duration_ms / 1000.0)

