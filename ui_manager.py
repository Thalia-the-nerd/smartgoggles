from PIL import Image, ImageDraw, ImageFont
import os
import time

# --- UI Configuration ---
FONT_PATH = os.path.join(os.path.dirname(__file__), 'VCR_OSD_MONO.ttf')

class UIManager:
    """
    Manages all drawing operations, now with a prompt for manual waypoint advance.
    """
    def __init__(self, disp):
        self.disp = disp
        self.width = disp.width
        self.height = disp.height
        
        try:
            self.font_small = ImageFont.truetype(FONT_PATH, 12)
            self.font_large = ImageFont.truetype(FONT_PATH, 16)
        except IOError:
            print(f"ERROR: Font file not found at {FONT_PATH}. Using default font.")
            self.font_small = ImageFont.load_default()
            self.font_large = ImageFont.load_default()

    def _create_base_image(self):
        return Image.new('1', (self.width, self.height), "WHITE")

    def _display_image(self, image):
        self.disp.ShowImage(self.disp.getbuffer(image.rotate(180)))

    def _draw_page_indicator(self, draw, page_name, sub_page_info=None):
        indicator_text = f"< {page_name.upper()} >"
        if sub_page_info:
            indicator_text = f"< {page_name.upper()} ({sub_page_info}) >"
        
        text_bbox = draw.textbbox((0, 0), indicator_text, font=self.font_small)
        text_width = text_bbox[2] - text_bbox[0]
        x = (self.width - text_width) / 2
        y = self.height - 14
        draw.text((x, y), indicator_text, font=self.font_small, fill=0)

    def display_home_screen(self, speed_kph, alt_m, gps_fix, time_str, is_recording=False):
        # ... (function content is unchanged) ...
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        gps_status_text = "GPS: OK" if gps_fix else "GPS: NO FIX"
        draw.text((2, 2), gps_status_text, font=self.font_small, fill=0)
        draw.text((self.width - 45, 2), time_str, font=self.font_small, fill=0)
        if is_recording:
            draw.ellipse((self.width - 80, 2, self.width - 70, 12), fill=0)
            draw.text((self.width - 110, 2), "REC", font=self.font_small, fill=0)
        draw.line([(0, 15), (self.width, 15)], fill=0)
        draw.text((5, 20), f"{speed_kph:.1f}", font=self.font_large, fill=0)
        draw.text((5, 40), "kph", font=self.font_small, fill=0)
        draw.text((self.width - 50, 20), f"{alt_m:.0f}", font=self.font_large, fill=0)
        draw.text((self.width - 50, 40), "m", font=self.font_small, fill=0)
        self._draw_page_indicator(draw, "HOME")
        self._display_image(image)

    def display_current_weather_screen(self, weather_data):
        # ... (function content is unchanged) ...
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        temp = weather_data.get('current_temp', 'N/A')
        condition = weather_data.get('forecast_condition', 'Loading...')
        updated = weather_data.get('last_updated', '--:--')
        draw.text((2, 2), "CURRENT WEATHER", font=self.font_small, fill=0)
        draw.text((self.width - 40, 2), f"@{updated}", font=self.font_small, fill=0)
        draw.line([(0, 15), (self.width, 15)], fill=0)
        draw.text((5, 25), condition, font=self.font_large, fill=0)
        draw.text((5, 45), f"Temp: {temp}", font=self.font_small, fill=0)
        self._draw_page_indicator(draw, "WEATHER", sub_page_info="1/2")
        self._display_image(image)

    def display_snow_report_screen(self, weather_data):
        # ... (function content is unchanged) ...
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        snow = weather_data.get('snowfall_today', 'N/A')
        updated = weather_data.get('last_updated', '--:--')
        draw.text((2, 2), "SNOW REPORT", font=self.font_small, fill=0)
        draw.text((self.width - 40, 2), f"@{updated}", font=self.font_small, fill=0)
        draw.line([(0, 15), (self.width, 15)], fill=0)
        draw.text((5, 25), "24h Snowfall:", font=self.font_large, fill=0)
        draw.text((5, 45), snow, font=self.font_small, fill=0)
        self._draw_page_indicator(draw, "WEATHER", sub_page_info="2/2")
        self._display_image(image)

    def display_now_playing_screen(self, track_name, is_playing):
        # ... (function content is unchanged) ...
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        draw.text((2, 2), "NOW PLAYING", font=self.font_small, fill=0)
        draw.line([(0, 15), (self.width, 15)], fill=0)
        if len(track_name) > 20: track_name = track_name[:18] + "..."
        draw.text((5, 20), track_name, font=self.font_small, fill=0)
        status_text = "Status: Playing" if is_playing else "Status: Paused"
        draw.text((5, 35), status_text, font=self.font_small, fill=0)
        controls_text = "8:Next 2:Prev 5:Play/Pause"
        draw.text((5, 50), controls_text, font=self.font_small, fill=0)
        self._draw_page_indicator(draw, "MUSIC", sub_page_info="1/2")
        self._display_image(image)
        
    def display_playlist_screen(self, playlists, current_playlist):
        # ... (function content is unchanged) ...
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        draw.text((2, 2), "SELECT PLAYLIST", font=self.font_small, fill=0)
        draw.line([(0, 15), (self.width, 15)], fill=0)
        y_pos = 20
        for name in playlists:
            prefix = "> " if name == current_playlist else "  "
            draw.text((5, y_pos), prefix + name, font=self.font_small, fill=0)
            y_pos += 15
            if y_pos > self.height - 20: break
        self._draw_page_indicator(draw, "MUSIC", sub_page_info="2/2")
        self._display_image(image)

    def display_navigation_screen(self, next_waypoint_info, is_main_page=True, active_route=None, gps_fix=False):
        """
        Displays the navigation screen, showing a manual advance prompt if GPS is unavailable.
        """
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        draw.text((2, 2), "NAVIGATION", font=self.font_small, fill=0)
        draw.line([(0, 15), (self.width, 15)], fill=0)

        if next_waypoint_info:
            wp_name = next_waypoint_info['name']
            draw.text((5, 20), f"{wp_name}", font=self.font_small, fill=0)

            # Check if distance is available (i.e., we have GPS)
            if 'distance_m' in next_waypoint_info:
                wp_dist_m = next_waypoint_info['distance_m']
                draw.text((5, 35), f"{wp_dist_m:.0f} m", font=self.font_large, fill=0)
            else: # No distance means no GPS
                draw.text((5, 35), "No GPS Signal", font=self.font_small, fill=0)
                draw.text((5, 50), "Press '+' to advance", font=self.font_small, fill=0)

            if active_route and active_route.get('is_ghost_race'):
                # ... (Ghost mode display logic is unchanged) ...
                pass
        else:
            draw.text((20, 35), "No Active", font=self.font_large, fill=0)
            draw.text((20, 50), "Route", font=self.font_large, fill=0)
            
        if is_main_page:
            self._draw_page_indicator(draw, "NAVIGATION")
            
        self._display_image(image)
        
    def display_summary_screen(self, summary_data):
        # ... (function content is unchanged) ...
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        draw.text((2, 2), "TRIP SUMMARY", font=self.font_small, fill=0)
        draw.line([(0, 15), (self.width, 15)], fill=0)
        vert_m = summary_data.get('total_vertical_m', 0)
        top_kph = summary_data.get('top_speed_kph', 0)
        draw.text((5, 20), "Vertical:", font=self.font_small, fill=0)
        draw.text((70, 20), f"{vert_m:.0f} m", font=self.font_small, fill=0)
        draw.text((5, 35), "Top Speed:", font=self.font_small, fill=0)
        draw.text((70, 35), f"{top_kph:.1f} kph", font=self.font_small, fill=0)
        self._draw_page_indicator(draw, "STATS")
        self._display_image(image)
        
    def display_menu(self, title, items, page_indicator=None):
        # ... (function content is unchanged) ...
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)
        draw.text((2, 2), title.upper(), font=self.font_small, fill=0)
        draw.line([(0, 15), (self.width, 15)], fill=0)
        y_pos = 20
        for item in items:
            draw.text((5, y_pos), item['name'], font=self.font_small, fill=0)
            y_pos += 15
            if y_pos > self.height - 15: break
        if page_indicator:
            self._draw_page_indicator(draw, page_indicator)
        self._display_image(image)

    def display_message(self, message, duration_ms):
        # ... (function content is unchanged) ...
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

