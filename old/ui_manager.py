from PIL import Image, ImageDraw, ImageFont
import os
import time
import datetime

# This path assumes the font file is in the same directory as the script.
# Using a clear, fixed-width font is important for readability on a small screen.
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VCR_OSD_MONO.ttf")

class UIManager:
    """
    Manages all display-related functions and drawing operations for the OLED screen.
    """
    def __init__(self, oled):
        """
        Initializes the UI Manager with the display object and loads fonts.
        """
        self.oled = oled
        self.width = oled.width
        self.height = oled.height
        
        self.image = Image.new("1", (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)
        
        try:
            self.font_large = ImageFont.truetype(FONT_PATH, 24)
            self.font_medium = ImageFont.truetype(FONT_PATH, 16)
            self.font_small = ImageFont.truetype(FONT_PATH, 12)
        except IOError:
            print("UI_MANAGER: Font file not found. Using default font.")
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def _clear_display(self):
        """Internal helper to clear the drawing canvas."""
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

    def display_home_screen(self, gps_data, data_lock):
        """Draws the main dashboard screen with real-time GPS and system data."""
        self._clear_display()
        
        with data_lock:
            fix = gps_data.get('fix', False)
            speed_mps = gps_data.get('speed', 0.0)
            alt_m = gps_data.get('alt', 0.0)
            sats = gps_data.get('sats', 0)

        # Draw GPS Status & Time
        gps_status_text = f"GPS: {sats} sats" if fix else "GPS: NO FIX"
        current_time = datetime.datetime.now().strftime("%H:%M")
        self.draw.text((0, 0), gps_status_text, font=self.font_small, fill=255)
        bbox = self.draw.textbbox((0,0), current_time, font=self.font_small)
        self.draw.text((self.width - (bbox[2]-bbox[0]), 0), current_time, font=self.font_small, fill=255)

        # Draw Speed (MPH)
        speed_mph = speed_mps * 2.23694
        speed_text = f"{speed_mph:.1f}"
        bbox = self.draw.textbbox((0,0), speed_text, font=self.font_large)
        speed_width, speed_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        speed_x = (self.width - speed_width) // 2
        speed_y = (self.height - speed_height) // 2 - 5
        self.draw.text((speed_x, speed_y), speed_text, font=self.font_large, fill=255)
        self.draw.text((speed_x + speed_width + 5, speed_y + 8), "mph", font=self.font_small, fill=255)

        # Draw Altitude (FT)
        alt_ft = alt_m * 3.28084
        alt_text = f"ALT: {alt_ft:,.0f} FT"
        self.draw.text((0, 52), alt_text, font=self.font_small, fill=255)
        
        self.oled.image(self.image)
        self.oled.show()

    def display_navigation_screen(self, next_waypoint_info):
        """Displays the current navigation target and distance."""
        self._clear_display()
        self.draw.text((0,0), "NAVIGATION", font=self.font_small, fill=255)
        self.draw.line([(0,12), (self.width, 12)], fill=100)
        
        if next_waypoint_info and next_waypoint_info.get('name'):
            waypoint_name = next_waypoint_info.get('name', 'N/A')
            distance_m = next_waypoint_info.get('distance', 0)
            distance_ft = distance_m * 3.28084
            
            self.draw.text((5, 20), "NEXT:", font=self.font_medium, fill=255)
            self.draw.text((5, 36), f" {waypoint_name}", font=self.font_medium, fill=255)
            self.draw.text((0, 52), f"DIST: {distance_ft:,.0f} FT", font=self.font_small, fill=255)
        else:
            self.draw.text((5, 30), "No Route", font=self.font_medium, fill=255)
            self.draw.text((5, 46), "Selected", font=self.font_medium, fill=255)

        self.oled.image(self.image)
        self.oled.show()

    def display_summary_screen(self, summary_data):
        """Displays the summary of the entire trip."""
        self._clear_display()
        self.draw.text((0,0), "TRIP SUMMARY", font=self.font_small, fill=255)
        self.draw.line([(0,12), (self.width, 12)], fill=100)

        total_vert_ft = summary_data.get('total_vert', 0) * 3.28084
        max_speed_mph = summary_data.get('max_speed', 0) * 2.23694
        runs_completed = summary_data.get('runs', 0)

        self.draw.text((5, 18), f"VERT: {total_vert_ft:,.0f} FT", font=self.font_medium, fill=255)
        self.draw.text((5, 34), f"TOP SPD: {max_speed_mph:.1f} MPH", font=self.font_medium, fill=255)
        self.draw.text((5, 50), f"RUNS: {runs_completed}", font=self.font_medium, fill=255)
        
        self.oled.image(self.image)
        self.oled.show()

    def display_menu(self, title, menu_items, selected_index):
        """Displays a generic, scrollable menu."""
        self._clear_display()
        self.draw.text((0,0), title.upper(), font=self.font_small, fill=255)
        self.draw.line([(0,12), (self.width, 12)], fill=100)
        
        display_start_index = 0
        if selected_index >= 3:
            display_start_index = selected_index - 3

        for i, item in enumerate(menu_items[display_start_index:display_start_index+4]):
            display_y = 16 + (i * 12)
            if (i + display_start_index) == selected_index:
                self.draw.text((0, display_y), ">", font=self.font_small, fill=255)
            self.draw.text((8, display_y), item, font=self.font_small, fill=255)

        self.oled.image(self.image)
        self.oled.show()

    def display_message(self, line1, line2="", duration_s=2):
        """Displays a simple, centered one or two-line message."""
        self._clear_display()
        bbox1 = self.draw.textbbox((0,0), line1, font=self.font_medium)
        self.draw.text(((self.width - (bbox1[2]-bbox1[0]))//2, 15), line1, font=self.font_medium, fill=255)
        if line2:
            bbox2 = self.draw.textbbox((0,0), line2, font=self.font_medium)
            self.draw.text(((self.width - (bbox2[2]-bbox2[0]))//2, 35), line2, font=self.font_medium, fill=255)
        
        self.oled.image(self.image)
        self.oled.show()
        if duration_s > 0:
            time.sleep(duration_s)

