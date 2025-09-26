from PIL import Image, ImageDraw, ImageFont
import os
import time
import math

# --- UI Configuration ---
FONT_PATH = os.path.join(os.path.dirname(__file__), 'VCR_OSD_MONO.ttf')

class UIManager:
    """
    Manages all drawing operations for the Smart Goggles UI.
    Includes a persistent header, splash screen, and enhanced data displays.
    """
    def __init__(self, disp):
        self.disp = disp
        self.width = disp.width
        self.height = disp.height
        
        try:
            self.font_small = ImageFont.truetype(FONT_PATH, 12)
            self.font_large = ImageFont.truetype(FONT_PATH, 16)
            self.font_xlarge = ImageFont.truetype(FONT_PATH, 24)
        except IOError:
            print(f"ERROR: Font file not found at {FONT_PATH}. Using default font.")
            self.font_small = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
            self.font_xlarge = ImageFont.load_default()

    def _create_base_image(self):
        """Creates a blank, black-and-white image buffer."""
        return Image.new('1', (self.width, self.height), "WHITE")

    def _display_image(self, image):
        """Rotates and displays the image buffer on the physical screen."""
        self.disp.ShowImage(self.disp.getbuffer(image.rotate(180)))

    def _draw_persistent_header(self, draw, gps_fix, time_str, is_recording):
        """Draws the top status bar, now used on all screens."""
        gps_status_text = "GPS: OK" if gps_fix else "GPS: NO FIX"
        draw.text((2, 2), gps_status_text, font=self.font_small, fill=0)
        draw.text((self.width - 45, 2), time_str, font=self.font_small, fill=0)
        if is_recording:
            draw.ellipse((self.width - 80, 2, self.width - 70, 12), fill=0)
            draw.text((self.width - 110, 2), "REC", font=self.font_small, fill=0)
        draw.line([(0, 15), (self.width, 15)], fill=0)

    def _draw_page_indicator(self, draw, page_name, sub_page_info=None):
        """Draws the '< PAGE >' indicator at the bottom of the screen."""
        indicator_text = f"< {page_name.upper()} >"
        if sub_page_info:
            indicator_text = f"< {page_name.upper()} ({sub_page_info}) >"
        
        text_bbox = draw.textbbox((0, 0), indicator_text, font=self.font_small)
        text_width = text_bbox[2] - text_bbox[0]
        x = (self.width - text_width) / 2
        y = self.height - 14
        draw.text((x, y), indicator_text, font=self.font_small, fill=0)

    def display_splash_screen(self):
        """Displays a startup splash screen."""
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        
        logo_text = "Smart Goggles"
        text_bbox = draw.textbbox((0, 0), logo_text, font=self.font_large)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        x = (self.width - text_width) / 2
        y = (self.height - text_height) / 2
        draw.text((x, y), logo_text, font=self.font_large, fill=0)
        
        self._display_image(image)
        time.sleep(2.5)

    def display_home_screen(self, speed_kph, alt_m, gps_fix, time_str, is_recording, incline_deg, time_to_last_lift_seconds):
        """Displays the main home screen with all primary data points."""
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        
        self._draw_persistent_header(draw, gps_fix, time_str, is_recording)

        # --- Main Data ---
        draw.text((5, 20), f"{speed_kph:.1f}", font=self.font_large, fill=0)
        draw.text((5, 40), "kph", font=self.font_small, fill=0)
        
        draw.text((self.width - 50, 20), f"{alt_m:.0f}", font=self.font_large, fill=0)
        draw.text((self.width - 50, 40), "m", font=self.font_small, fill=0)
        
        # --- Incline Meter ---
        draw.text((5, 55), f"SLOPE: {incline_deg:.0f} deg", font=self.font_small, fill=0)

        # --- Last Lift Countdown Timer ---
        if time_to_last_lift_seconds is not None and time_to_last_lift_seconds > 0:
            mins, secs = divmod(int(time_to_last_lift_seconds), 60)
            countdown_text = f"CLOSE: {mins:02d}:{secs:02d}"
            text_bbox = draw.textbbox((0, 0), countdown_text, font=self.font_small)
            text_width = text_bbox[2] - text_bbox[0]
            draw.text(((self.width - text_width) / 2, 55), countdown_text, font=self.font_small, fill=0)
        
        self._draw_page_indicator(draw, "HOME")
        self._display_image(image)

    def display_compass_screen(self, heading, gps_fix, time_str, is_recording):
        """Displays a digital compass with the persistent header."""
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        self._draw_persistent_header(draw, gps_fix, time_str, is_recording)

        if gps_fix:
            dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
            cardinal = dirs[math.floor((heading + 22.5) / 45) % 8]
            heading_text = f"{heading:.0f}"
            
            text_bbox = draw.textbbox((0, 0), heading_text, font=self.font_xlarge)
            text_width = text_bbox[2] - text_bbox[0]
            draw.text(((self.width - text_width) / 2, 20), heading_text, font=self.font_xlarge, fill=0)

            text_bbox = draw.textbbox((0, 0), cardinal, font=self.font_large)
            text_width = text_bbox[2] - text_bbox[0]
            draw.text(((self.width - text_width) / 2, 45), cardinal, font=self.font_large, fill=0)
        else:
            draw.text((20, 35), "No GPS Signal", font=self.font_large, fill=0)

        self._draw_page_indicator(draw, "COMPASS")
        self._display_image(image)

    def display_achievements_screen(self, bests, gps_fix, time_str, is_recording):
        """Displays the 'Day's Best' achievements with the persistent header."""
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        self._draw_persistent_header(draw, gps_fix, time_str, is_recording)
        y_pos = 18

        if not bests or not any(bests.values()):
            draw.text((5, 35), "No runs logged yet.", font=self.font_small, fill=0)
        else:
            if bests.get('longest_run'):
                duration = bests['longest_run']['duration_seconds']
                run_name = bests['longest_run']['run_name']
                draw.text((2, y_pos), f"TIME: {duration/60:.0f}m {duration%60:.0f}s on {run_name[:8]}", font=self.font_small, fill=0)
                y_pos += 15
            
            if bests.get('biggest_vertical'):
                vert = bests['biggest_vertical']['vertical_m']
                run_name = bests['biggest_vertical']['run_name']
                draw.text((2, y_pos), f"VERT: {vert:.0f}m on {run_name[:10]}", font=self.font_small, fill=0)
                y_pos += 15

            if bests.get('fastest_run'):
                speed = bests['fastest_run']['top_speed_kph']
                run_name = bests['fastest_run']['run_name']
                draw.text((2, y_pos), f"SPD: {speed:.1f}kph on {run_name[:8]}", font=self.font_small, fill=0)

        self._draw_page_indicator(draw, "ACHIEVEMENTS")
        self._display_image(image)

    def display_current_weather_screen(self, weather_data, gps_fix, time_str, is_recording):
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        self._draw_persistent_header(draw, gps_fix, time_str, is_recording)
        
        temp = weather_data.get('current_temp', 'N/A')
        condition = weather_data.get('forecast_condition', 'Loading...')
        updated = weather_data.get('last_updated', '--:--')
        
        draw.text((5, 25), condition, font=self.font_large, fill=0)
        draw.text((5, 45), f"Temp: {temp}", font=self.font_small, fill=0)
        draw.text((self.width - 40, 55), f"@{updated}", font=self.font_small, fill=0)

        self._draw_page_indicator(draw, "WEATHER", sub_page_info="1/2")
        self._display_image(image)

    def display_snow_report_screen(self, weather_data, gps_fix, time_str, is_recording):
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        self._draw_persistent_header(draw, gps_fix, time_str, is_recording)

        snow = weather_data.get('snowfall_today', 'N/A')
        updated = weather_data.get('last_updated', '--:--')

        draw.text((5, 25), "24h Snowfall:", font=self.font_large, fill=0)
        draw.text((5, 45), snow, font=self.font_small, fill=0)
        draw.text((self.width - 40, 55), f"@{updated}", font=self.font_small, fill=0)

        self._draw_page_indicator(draw, "WEATHER", sub_page_info="2/2")
        self._display_image(image)
        
    def display_navigation_screen(self, next_waypoint_info, time_str, is_recording, is_main_page=True, active_route=None, gps_fix=False, poi_info=None):
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        self._draw_persistent_header(draw, gps_fix, time_str, is_recording)

        target_info = next_waypoint_info or poi_info

        if target_info:
            wp_name = target_info['name']
            if len(wp_name) > 20: wp_name = wp_name[:18] + "..."
            draw.text((5, 20), f"{wp_name}", font=self.font_small, fill=0)

            if 'distance_m' in target_info and gps_fix:
                wp_dist_m = target_info['distance_m']
                draw.text((5, 35), f"{wp_dist_m:.0f} m", font=self.font_large, fill=0)
            elif not gps_fix:
                draw.text((5, 35), "No GPS Signal", font=self.font_small, fill=0)
            else:
                 draw.text((5, 35), "Press '/' to advance", font=self.font_small, fill=0)
        else:
            draw.text((20, 35), "No Active", font=self.font_large, fill=0)
            draw.text((20, 50), "Route", font=self.font_large, fill=0)
            
        if is_main_page:
            self._draw_page_indicator(draw, "NAVIGATION")
            
        self._display_image(image)
        
    def display_summary_screen(self, summary_data, gps_fix, time_str, is_recording):
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        self._draw_persistent_header(draw, gps_fix, time_str, is_recording)
        
        vert_m = summary_data.get('total_vertical_m', 0)
        top_kph = summary_data.get('top_speed_kph', 0)
        draw.text((5, 20), "Vertical:", font=self.font_small, fill=0)
        draw.text((70, 20), f"{vert_m:.0f} m", font=self.font_small, fill=0)
        draw.text((5, 35), "Top Speed:", font=self.font_small, fill=0)
        draw.text((70, 35), f"{top_kph:.1f} kph", font=self.font_small, fill=0)
        self._draw_page_indicator(draw, "STATS")
        self._display_image(image)

    def display_run_logbook_screen(self, log_entries, page_num, total_pages, gps_fix, time_str, is_recording):
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        self._draw_persistent_header(draw, gps_fix, time_str, is_recording)

        title = "RUN LOGBOOK"
        if total_pages > 0:
            title = f"LOG ({page_num}/{total_pages})"
        
        y_pos = 20
        if not log_entries:
            draw.text((5, 35), "No runs logged yet.", font=self.font_small, fill=0)
        else:
            for entry in log_entries:
                run_name = entry['run_name']
                if len(run_name) > 10: run_name = run_name[:9] + "..."
                duration = entry['duration_seconds']
                vert = entry['vertical_m']
                draw.text((2, y_pos), f"@{entry['time']} {run_name} {duration/60:.0f}m {vert:.0f}m", font=self.font_small, fill=0)
                y_pos += 15

        self._draw_page_indicator(draw, title)
        self._display_image(image)

    def display_run_analytics_screen(self, analytics, gps_fix, time_str, is_recording):
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        self._draw_persistent_header(draw, gps_fix, time_str, is_recording)
        
        run_name = analytics.get('run_name', 'Run')
        draw.text((2, 18), f"{run_name[:16]} Stats", font=self.font_small, fill=0)
        
        duration = analytics.get('duration', 0)
        vert = analytics.get('vertical', 0)
        top_speed = analytics.get('top_speed', 0)

        draw.text((5, 30), f"Time: {duration/60:.0f}m {duration%60:.0f}s", font=self.font_small, fill=0)
        draw.text((5, 42), f"Vertical: {vert:.0f} m", font=self.font_small, fill=0)
        draw.text((5, 54), f"Top Speed: {top_speed:.1f} kph", font=self.font_small, fill=0)
        self._display_image(image)
        
    def display_menu(self, title, items, gps_fix, time_str, is_recording, page_indicator=None):
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        self._draw_persistent_header(draw, gps_fix, time_str, is_recording)
        
        y_pos = 20
        for item in items:
            draw.text((5, y_pos), item['name'], font=self.font_small, fill=0)
            y_pos += 15
            if y_pos > self.height - 15: break
        if page_indicator:
            self._draw_page_indicator(draw, page_indicator)
        else:
            self._draw_page_indicator(draw, title)

        self._display_image(image)

    def display_message(self, message, duration_ms):
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        text_bbox = draw.textbbox((0, 0), message, font=self.font_large)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        x = (self.width - text_width) / 2
        y = (self.height - text_height) / 2
        draw.text((x, y), message, font=self.font_large, fill=0)
        self._display_image(image)
        time.sleep(duration_ms / 1000.0)


