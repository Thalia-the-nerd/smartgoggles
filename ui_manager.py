import os
import time
from PIL import Image, ImageDraw, ImageFont

# --- UI Configuration ---
FONT_PATH = os.path.join(os.path.dirname(__file__), 'VCR_OSD_MONO.ttf')

# --- Weather Icon Mapping ---
WEATHER_ICONS = {
    "Clear": "O", "Cloudy": "C", "Fog": "F", "Rain": "R",
    "Snow": "*", "T-Storm": "T", "Mixed": "?", "Loading...": "...",
    "Unknown": "?", "Network Error": "X"
}

class UIManager:
    """Manages all drawing operations for the Smart Goggles UI."""
    def __init__(self, disp):
        self.disp = disp
        self.width = disp.width
        self.height = disp.height
        
        try:
            self.font_small = ImageFont.truetype(FONT_PATH, 12)
            self.font_large = ImageFont.truetype(FONT_PATH, 16)
            self.font_xl = ImageFont.truetype(FONT_PATH, 24)
        except IOError:
            print(f"ERROR: Font file not found at {FONT_PATH}. Using default font.")
            self.font_small = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
            self.font_xl = ImageFont.load_default()

    def _create_base_image_and_draw(self):
        """Creates a blank image and a draw object."""
        image = Image.new('1', (self.width, self.height), "WHITE")
        return image, ImageDraw.Draw(image)

    def _display_image(self, image):
        """Rotates the final image 180 degrees and displays it."""
        self.disp.ShowImage(self.disp.getbuffer(image.rotate(180)))

    def _draw_header(self, draw, header_data):
        """Draws the persistent top status bar."""
        gps_fix = header_data.get('gps_fix', False)
        time_str = header_data.get('time_str', '--:--:--')
        is_recording = header_data.get('is_recording', False)

        gps_status_text = "GPS" if gps_fix else "NO GPS"
        draw.text((2, 2), gps_status_text, font=self.font_small, fill=0)
        
        time_bbox = draw.textbbox((0, 0), time_str, font=self.font_small)
        time_width = time_bbox[2] - time_bbox[0]
        draw.text(((self.width - time_width) / 2, 2), time_str, font=self.font_small, fill=0)

        if is_recording:
            rec_text = "REC"
            rec_bbox = draw.textbbox((0, 0), rec_text, font=self.font_small)
            rec_width = rec_bbox[2] - rec_bbox[0]
            draw.ellipse((self.width - rec_width - 10, 4, self.width - rec_width, 14), fill=0)
            draw.text((self.width - rec_width - 2, 2), rec_text, font=self.font_small, fill=0)
            
        draw.line([(0, 18), (self.width, 18)], fill=0, width=2)

    def display_splash_screen(self):
        image, draw = self._create_base_image_and_draw()
        title_text = "SMART GOGGLES"
        version_text = "v1.1"
        
        title_bbox = draw.textbbox((0,0), title_text, font=self.font_large)
        draw.text(((self.width - title_bbox[2])/2, 20), title_text, font=self.font_large, fill=0)
        
        ver_bbox = draw.textbbox((0,0), version_text, font=self.font_small)
        draw.text(((self.width - ver_bbox[2])/2, 45), version_text, font=self.font_small, fill=0)
        
        self._display_image(image)
        time.sleep(2.5)

    def display_home_screen(self, speed_kph, alt_m, header_data):
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        
        speed_text = f"{speed_kph:.1f}"
        alt_text = f"{alt_m:.0f}"

        draw.text((5, 25), speed_text, font=self.font_xl, fill=0)
        draw.text((5, 50), "kph", font=self.font_small, fill=0)
        
        alt_bbox = draw.textbbox((0,0), alt_text, font=self.font_xl)
        draw.text((self.width - alt_bbox[2] - 5, 25), alt_text, font=self.font_xl, fill=0)
        draw.text((self.width - 30, 50), "m", font=self.font_small, fill=0)

        self._display_image(image)

    def display_compass_screen(self, heading, header_data):
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        if not header_data.get('gps_fix'):
            draw.text((20, 35), "NO SIGNAL", font=self.font_large, fill=0)
        else:
            heading_text = f"{heading:.0f}"
            cardinal_dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"]
            cardinal = cardinal_dirs[int(round(heading / 45))]
            heading_bbox = draw.textbbox((0,0), heading_text, font=self.font_xl)
            draw.text(((self.width - heading_bbox[2]) / 2, 25), heading_text, font=self.font_xl, fill=0)
            cardinal_bbox = draw.textbbox((0,0), cardinal, font=self.font_large)
            draw.text(((self.width - cardinal_bbox[2]) / 2, 50), cardinal, font=self.font_large, fill=0)
        self._display_image(image)

    def display_performance_profile_screen(self, profile_data, header_data):
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        relaxed = profile_data.get('relaxed_time', 0)
        cruising = profile_data.get('cruising_time', 0)
        aggressive = profile_data.get('aggressive_time', 0)
        total = relaxed + cruising + aggressive
        if total == 0:
            draw.text((20, 35), "NO DATA", font=self.font_large, fill=0)
        else:
            agg_pct = (aggressive / total) * 100
            cruise_pct = (cruising / total) * 100
            draw.text((5, 25), f"Aggressive: {agg_pct:.0f}%", font=self.font_large, fill=0)
            draw.text((5, 45), f"Cruising: {cruise_pct:.0f}%", font=self.font_large, fill=0)
        self._display_image(image)

    def display_achievements_screen(self, bests_data, header_data):
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        fastest_run = bests_data.get('fastest_run')
        if fastest_run:
            speed = fastest_run['top_speed_kph']
            draw.text((5, 25), f"Top Speed: {speed:.1f} kph", font=self.font_large, fill=0)
        else:
            draw.text((5, 25), "Top Speed: N/A", font=self.font_large, fill=0)
        biggest_drop = bests_data.get('biggest_drop')
        if biggest_drop:
            drop = biggest_drop['vertical_m']
            draw.text((5, 45), f"Big Drop: {drop:.0f} m", font=self.font_large, fill=0)
        else:
            draw.text((5, 45), "Big Drop: N/A", font=self.font_large, fill=0)
        self._display_image(image)

    def display_current_weather_screen(self, weather_data, header_data):
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        condition = weather_data.get('forecast_condition', 'Loading...')
        temp = weather_data.get('current_temp', 'N/A')
        icon = WEATHER_ICONS.get(condition, "?")
        icon_bbox = draw.textbbox((0,0), icon, font=self.font_xl)
        draw.text((15, 30), icon, font=self.font_xl, fill=0)
        draw.text((50, 25), f"{condition}", font=self.font_large, fill=0)
        draw.text((50, 45), f"Temp: {temp}", font=self.font_large, fill=0)
        self._display_image(image)

    def display_snow_report_screen(self, weather_data, header_data):
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        snow = weather_data.get('snowfall_today', 'N/A')
        draw.text((5, 25), "24h Snowfall:", font=self.font_large, fill=0)
        draw.text((5, 45), f"{snow}", font=self.font_large, fill=0)
        self._display_image(image)

    def display_summary_screen(self, summary_data, header_data):
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        vert_m = summary_data.get('total_vertical_m', 0)
        top_kph = summary_data.get('top_speed_kph', 0)
        draw.text((5, 25), f"Vertical: {vert_m:.0f} m", font=self.font_large, fill=0)
        draw.text((5, 45), f"Top Speed: {top_kph:.1f} kph", font=self.font_large, fill=0)
        self._display_image(image)

    def display_run_logbook_screen(self, log_entries, header_data):
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        if not log_entries:
            draw.text((20, 35), "NO RUNS LOGGED", font=self.font_large, fill=0)
        else:
            y_pos = 25
            for entry in log_entries:
                run_name = entry['run_name']
                if len(run_name) > 12: run_name = run_name[:11] + "..."
                duration = entry['duration_seconds']
                minutes, seconds = divmod(duration, 60)
                time_str = f"{int(minutes):02}:{int(seconds):02}"
                draw.text((5, y_pos), run_name, font=self.font_large, fill=0)
                time_bbox = draw.textbbox((0,0), time_str, font=self.font_large)
                draw.text((self.width - time_bbox[2] - 5, y_pos), time_str, font=self.font_large, fill=0)
                y_pos += 20
        self._display_image(image)

    def display_navigation_screen(self, next_waypoint_info, header_data, is_main_page=True):
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        
        if next_waypoint_info:
            name = next_waypoint_info['name']
            if len(name) > 18: name = name[:17] + "..."
            draw.text((5, 25), f"{name}", font=self.font_large, fill=0)
            if 'distance_m' in next_waypoint_info and header_data.get('gps_fix'):
                dist = next_waypoint_info['distance_m']
                draw.text((5, 45), f"{dist:.0f} m", font=self.font_large, fill=0)
            else:
                 draw.text((5, 45), "NO GPS SIGNAL", font=self.font_small, fill=0)
        elif is_main_page:
            draw.text((20, 35), "NO ACTIVE ROUTE", font=self.font_large, fill=0)
        
        self._display_image(image)
        
    def display_id_entry_screen(self, prompt, id_buffer, waypoint_name, header_data):
        """Displays the screen for entering a waypoint ID."""
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        
        draw.text((5, 25), f"{prompt}: {id_buffer}", font=self.font_large, fill=0)
        
        name_to_display = waypoint_name if waypoint_name else "..."
        if len(name_to_display) > 18: name_to_display = name_to_display[:17] + "..."
        draw.text((5, 45), name_to_display, font=self.font_large, fill=0)

        self._display_image(image)

    def display_ski_patrol_screen(self, phone_number, header_data):
        # (This function remains the same)
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        draw.text((5, 25), "SKI PATROL", font=self.font_large, fill=0)
        draw.text((5, 45), f"{phone_number}", font=self.font_large, fill=0)
        self._display_image(image)

    def display_diagnostic_screen(self, gps_data, header_data):
        # (This function remains the same)
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        lat = gps_data.get('lat', 0)
        lon = gps_data.get('lon', 0)
        draw.text((5, 25), f"Lat: {lat:.4f}", font=self.font_large, fill=0)
        draw.text((5, 45), f"Lon: {lon:.4f}", font=self.font_large, fill=0)
        self._display_image(image)
        
    def display_run_analytics_screen(self, analytics_data, header_data):
        # (This function remains the same)
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        run_name = analytics_data['run_name']
        if len(run_name) > 18: run_name = run_name[:17] + "..."
        draw.text((5, 25), run_name, font=self.font_large, fill=0)
        duration = analytics_data['duration_seconds']
        minutes, seconds = divmod(duration, 60)
        time_str = f"Time: {int(minutes):02}:{int(seconds):02}"
        draw.text((5, 45), time_str, font=self.font_large, fill=0)
        if analytics_data.get('personal_best'):
            pb_text = "NEW PB!"
            pb_bbox = draw.textbbox((0,0), pb_text, font=self.font_small)
            draw.rectangle((self.width - pb_bbox[2] - 8, 43, self.width, 63), fill=0)
            draw.text((self.width - pb_bbox[2] - 5, 45), pb_text, font=self.font_small, fill=255)
        self._display_image(image)

    def display_menu(self, title, items, header_data):
        # (This function remains the same)
        image, draw = self._create_base_image_and_draw()
        self._draw_header(draw, header_data)
        y_pos = 25
        for item in items:
            draw.text((5, y_pos), item['name'], font=self.font_large, fill=0)
            y_pos += 20
        self._display_image(image)

    def display_message(self, message, duration_ms):
        # (This function remains the same)
        image, draw = self._create_base_image_and_draw()
        bbox = draw.textbbox((0,0), message, font=self.font_large)
        draw.text(((self.width - bbox[2])/2, (self.height-bbox[3])/2), message, font=self.font_large, fill=0)
        self._display_image(image)
        time.sleep(duration_ms / 1000.0)


