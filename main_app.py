import time
from datetime import datetime, timedelta
import evdev
import select
import queue
import threading
import math

# Import project modules
import db_manager
import mapper
from ui_manager import UIManager
from recorder import VideoRecorder
import weather_handler
import variables # Import the new variables file
import audio_handler

# --- CONFIGURATION ---
KEYPAD_DEVICE_PATH = "/dev/input/by-id/usb-SEMICO_USB_Keyboard-event-kbd"
ITEMS_PER_PAGE = 3
LOGBOOK_ITEMS_PER_PAGE = 3
AUTO_SCROLL_DELAY = 3.0
AUTO_SCROLL_INTERVAL = 2.0
ANALYTICS_DISPLAY_DURATION = 5.0
AUTO_RETURN_SECONDS = 10.0 # Time before returning from a sub-page

KEY_MAP = {
    79: '1', 80: '2', 81: '3', 75: '4', 76: '5', 77: '6',
    71: '7', 72: '8', 73: '9', 55: 'BACK', 82: 'SAVE_WAYPOINT',
    73: 'RECORD_TOGGLE', 98: 'SKIP_WAYPOINT'
}

def main(disp, gps_queue, gps_data, data_lock, ui):
    """
    Main application with enhanced UI features.
    """
    # --- Initialization ---
    try:
        keypad = evdev.InputDevice(KEYPAD_DEVICE_PATH)
    except FileNotFoundError:
        print(f"FATAL ERROR: Keypad not found at {KEYPAD_DEVICE_PATH}")
        return
        
    recorder_data = {}
    recorder_data_lock = threading.Lock()
    recorder = VideoRecorder(gps_queue, recorder_data, recorder_data_lock)
    
    # --- Application State ---
    main_pages = ['HOME', 'COMPASS', 'ACHIEVEMENTS', 'WEATHER', 'STATS', 'LOGBOOK', 'NAVIGATION', 'DIRECTIONS']
    main_page_index = 0
    
    weather_sub_page_index = 0
    sub_page_enter_time = 0
    logbook_page = 0

    wizard_state = 'IDLE'; wizard_choices = {}; menu_items = []; full_menu_items = []; menu_page = 0
    active_route = None; next_waypoint_info = None; active_poi = None
    last_run_analytics = None; analytics_display_end_time = 0
    
    dirty = True 
    last_full_second_update = 0
    
    gps_data_cache = {}
    time_to_last_lift_seconds = None
    last_lift_warning_active = False

    try:
        while True:
            current_time = time.time()
            if current_time - last_full_second_update >= 1.0:
                dirty = True
                last_full_second_update = current_time

            # --- GPS Update & Position Tracking ---
            try:
                new_gps_data = gps_queue.get_nowait()
                gps_data_cache = new_gps_data.copy()
                dirty = True
                with data_lock:
                    gps_data.update(new_gps_data)
            except queue.Empty:
                pass
            
            # Extract latest data for use
            current_location = {'lat': gps_data_cache.get('lat'), 'lon': gps_data_cache.get('lon'), 'alt_m': gps_data_cache.get('alt_m')}
            speed_kph = gps_data_cache.get('speed_kph', 0)
            alt_m = gps_data_cache.get('alt_m', 0)
            gps_fix = gps_data_cache.get('fix', False)
            heading = gps_data_cache.get('heading', 0)
            incline_deg = gps_data_cache.get('incline_deg', 0)

            if active_route:
                update_result = mapper.update_position(active_route, current_location)
                if update_result:
                    if 'analytics' in update_result:
                        last_run_analytics = update_result['analytics']; analytics_display_end_time = current_time + ANALYTICS_DISPLAY_DURATION
                    next_waypoint_info = update_result.get('waypoint_info')
                else: 
                    ui.display_message("Route Finished!", 2000); active_route = None
                dirty = True
            elif active_poi and gps_fix:
                active_poi['distance_m'] = mapper.haversine_distance(current_location, active_poi)
                dirty = True

            if last_run_analytics and current_time > analytics_display_end_time:
                last_run_analytics = None; dirty = True

            if main_pages[main_page_index] == 'WEATHER' and weather_sub_page_index != 0:
                if current_time - sub_page_enter_time > AUTO_RETURN_SECONDS:
                    weather_sub_page_index = 0; dirty = True

            # --- Input Handling ---
            r, w, x = select.select([keypad], [], [], 0.05)
            if r:
                for event in keypad.read():
                    if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                        button = KEY_MAP.get(event.code)
                        if not button: continue
                        dirty = True
                        current_page_name = main_pages[main_page_index]
                        
                        if button == 'BACK':
                            if active_route or active_poi: active_route, next_waypoint_info, active_poi = None, None, None
                            elif last_run_analytics: last_run_analytics = None
                            elif wizard_state != 'IDLE': wizard_state, wizard_choices, menu_items, full_menu_items, menu_page = 'IDLE', {}, [], [], 0
                            continue
                        
                        if current_page_name == 'LOGBOOK':
                            # ... (Logbook pagination logic) ...
                            pass

                        if current_page_name == 'WEATHER':
                            if button == '8' or button == '2':
                                weather_sub_page_index = 1 - weather_sub_page_index
                                if weather_sub_page_index != 0: sub_page_enter_time = current_time

                        if wizard_state == 'IDLE' and not active_route and not active_poi:
                            if button == '4': main_page_index = (main_page_index - 1 + len(main_pages)) % len(main_pages); weather_sub_page_index = 0
                            elif button == '6': main_page_index = (main_page_index + 1) % len(main_pages); weather_sub_page_index = 0
                            elif button == 'RECORD_TOGGLE':
                                if recorder.is_recording(): recorder.stop()
                                else: recorder.start()
                            elif button == 'SAVE_WAYPOINT':
                                if gps_fix and current_location.get('lat'):
                                    db_manager.add_waypoint(f"WP {datetime.now().strftime('%H:%M')}", current_location['lat'], current_location['lon'], alt_m)
                                    ui.display_message("Waypoint Saved!", 1500)
                                else: ui.display_message("No GPS Fix!", 1500)
                            elif current_page_name == 'DIRECTIONS' and button == '5': wizard_state = 'SELECT_TYPE'
                            continue

                        # ... (Wizard logic remains here) ...

            # --- Display & State Logic ---
            if dirty:
                time_str = datetime.now().strftime("%H:%M")
                is_recording = recorder.is_recording()

                # --- Last Lift Warning Logic ---
                now = datetime.now()
                last_lift_dt = now.replace(hour=variables.LAST_LIFT_TIME[0], minute=variables.LAST_LIFT_TIME[1], second=0, microsecond=0)
                warning_30_min = last_lift_dt - timedelta(minutes=30)
                
                time_to_last_lift_seconds = None
                if now > warning_30_min and now < last_lift_dt:
                    time_to_last_lift_seconds = (last_lift_dt - now).total_seconds()
                    if not last_lift_warning_active:
                        audio_handler.speak("Lifts closing soon.")
                        last_lift_warning_active = True
                elif now > last_lift_dt:
                    last_lift_warning_active = False # Reset for next day

                # ... (Prepare Menus logic remains here) ...

                current_page_name = main_pages[main_page_index]
                if last_run_analytics:
                    ui.display_run_analytics_screen(last_run_analytics, gps_fix, time_str, is_recording)
                elif active_route or active_poi:
                    ui.display_navigation_screen(next_waypoint_info, time_str, is_recording, is_main_page=False, active_route=active_route, gps_fix=gps_fix, poi_info=active_poi)
                elif wizard_state != 'IDLE':
                    ui.display_menu(wizard_state.replace('_', ' ').title(), menu_items, gps_fix, time_str, is_recording)
                elif current_page_name == 'HOME':
                    ui.display_home_screen(speed_kph, alt_m, gps_fix, time_str, is_recording, incline_deg, time_to_last_lift_seconds)
                elif current_page_name == 'COMPASS':
                    ui.display_compass_screen(heading, gps_fix, time_str, is_recording)
                elif current_page_name == 'ACHIEVEMENTS':
                    ui.display_achievements_screen(db_manager.get_days_bests(), gps_fix, time_str, is_recording)
                elif current_page_name == 'WEATHER':
                    latest_weather = weather_handler.get_latest_weather()
                    if weather_sub_page_index == 0: ui.display_current_weather_screen(latest_weather, gps_fix, time_str, is_recording)
                    else: ui.display_snow_report_screen(latest_weather, gps_fix, time_str, is_recording)
                elif current_page_name == 'STATS':
                    ui.display_summary_screen(db_manager.get_trip_summary(), gps_fix, time_str, is_recording)
                elif current_page_name == 'LOGBOOK':
                    log_entries = db_manager.get_run_log_entries()
                    total_pages = math.ceil(len(log_entries) / LOGBOOK_ITEMS_PER_PAGE) if log_entries else 0
                    start = logbook_page * LOGBOOK_ITEMS_PER_PAGE
                    paginated = log_entries[start : start + LOGBOOK_ITEMS_PER_PAGE]
                    ui.display_run_logbook_screen(paginated, logbook_page + 1, total_pages, gps_fix, time_str, is_recording)
                elif current_page_name == 'NAVIGATION':
                    ui.display_navigation_screen(None, time_str, is_recording, is_main_page=True, gps_fix=gps_fix)
                elif current_page_name == 'DIRECTIONS':
                    ui.display_menu("Find Directions", [{'name': "Press 5 to start"}], gps_fix, time_str, is_recording, page_indicator="DIRECTIONS")

                dirty = False
            time.sleep(0.02)
            
    finally:
        if recorder.is_recording(): recorder.stop()
        keypad.close()


