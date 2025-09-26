import time
from datetime import datetime
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

# --- CONFIGURATION ---
KEYPAD_DEVICE_PATH = "/dev/input/by-id/usb-SEMICO_USB_Keyboard-event-kbd"
ITEMS_PER_PAGE = 3 
LOGBOOK_ITEMS_PER_PAGE = 3
AUTO_SCROLL_DELAY = 3.0 # Seconds to wait before starting auto-scroll
AUTO_SCROLL_INTERVAL = 2.0 # Seconds between each page turn
ANALYTICS_DISPLAY_DURATION = 5.0 # Seconds to show run analytics

KEY_MAP = {
    79: '1', 80: '2', 81: '3',
    75: '4', 76: '5', 77: '6',
    71: '7', 72: '8', 73: '9',
    55: 'BACK',
    82: 'SAVE_WAYPOINT',
    73: 'RECORD_TOGGLE',
    98: 'SKIP_WAYPOINT'
}

def main(disp, gps_queue, gps_data, data_lock):
    """
    Main application with new features: Compass, Achievements, Incline Meter, Last Lift Warning.
    """
    # --- Initialization ---
    try:
        keypad = evdev.InputDevice(KEYPAD_DEVICE_PATH)
        print(f"LOG: Successfully opened keypad: {keypad.name}")
    except FileNotFoundError:
        print(f"FATAL ERROR: Keypad not found at {KEYPAD_DEVICE_PATH}")
        return
        
    ui = UIManager(disp)
    recorder_data = {}
    recorder_data_lock = threading.Lock()
    recorder = VideoRecorder(gps_queue, recorder_data, recorder_data_lock)
    
    # --- Application State ---
    main_pages = ['HOME', 'COMPASS', 'WEATHER', 'STATS', 'ACHIEVEMENTS', 'LOGBOOK', 'NAVIGATION', 'DIRECTIONS']
    main_page_index = 0
    
    weather_sub_page_index = 0
    logbook_page = 0

    wizard_state = 'IDLE' 
    wizard_choices = {}   
    menu_items = []
    full_menu_items = []
    menu_page = 0

    active_route = None
    next_waypoint_info = None
    active_poi = None
    last_run_analytics = None
    analytics_display_end_time = 0
    dirty = True 
    
    auto_scroll_start_time = None
    last_auto_scroll_time = 0
    
    # GPS-derived data
    current_location, speed_kph, alt_m, gps_fix = {}, 0, 0, False
    heading, incline_deg = 0, 0
    
    all_runs_by_id = {run['id']: run for run in db_manager.get_all_runs_structured()}
    
    # Last lift warning state
    last_lift_warning_30_triggered = False
    last_lift_warning_15_triggered = False
    show_last_lift_warning = None # Will hold the message string

    try:
        while True:
            # --- GPS Update & Position Tracking ---
            try:
                new_gps_data = gps_queue.get_nowait()
                current_location = {
                    'lat': new_gps_data.get('lat'), 'lon': new_gps_data.get('lon'),
                    'alt_m': new_gps_data.get('alt_m', 0), 'speed_kph': new_gps_data.get('speed_kph', 0)
                }
                speed_kph = new_gps_data.get('speed_kph', 0)
                alt_m = new_gps_data.get('alt_m', 0)
                gps_fix = new_gps_data.get('fix', False)
                heading = new_gps_data.get('heading', 0)
                incline_deg = new_gps_data.get('incline_deg', 0)
                dirty = True
                with data_lock:
                    gps_data.update({
                        'fix': gps_fix, 'lat': current_location.get('lat'), 'lon': current_location.get('lon'),
                        'alt': alt_m, 'speed': new_gps_data.get('speed_mps', 0)
                    })
            except queue.Empty:
                pass

            # --- Last Lift Warning Logic ---
            now = datetime.now()
            last_lift_time = now.replace(hour=variables.LAST_LIFT_HOUR, minute=variables.LAST_LIFT_MINUTE, second=0, microsecond=0)
            
            time_to_last_lift = (last_lift_time - now).total_seconds()

            # 30-minute warning
            if not last_lift_warning_30_triggered and 900 < time_to_last_lift <= 1800:
                show_last_lift_warning = "30 MIN WARNING"
                last_lift_warning_30_triggered = True
                dirty = True
            
            # 15-minute warning
            elif not last_lift_warning_15_triggered and 0 < time_to_last_lift <= 900:
                show_last_lift_warning = "15 MIN WARNING"
                last_lift_warning_15_triggered = True
                dirty = True
                
            # Clear warning after a few seconds or if time has passed
            elif show_last_lift_warning and time_to_last_lift <= 0:
                 show_last_lift_warning = None
                 dirty = True

            if active_route:
                update_result = mapper.update_position(active_route, current_location)
                if update_result:
                    if 'analytics' in update_result:
                        last_run_analytics = update_result['analytics']
                        analytics_display_end_time = time.time() + ANALYTICS_DISPLAY_DURATION
                    next_waypoint_info = update_result.get('waypoint_info')
                else:
                    ui.display_message("Route Finished!", 2000)
                    active_route = None
                dirty = True
            elif active_poi and gps_fix:
                active_poi['distance_m'] = mapper.haversine_distance(current_location, active_poi)
                dirty = True

            if last_run_analytics and time.time() > analytics_display_end_time:
                last_run_analytics = None
                dirty = True

            # --- Input Handling (existing code is correct, not shown for brevity) ---
            r, w, x = select.select([keypad], [], [], 0.05)
            if r:
                for event in keypad.read():
                    if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                        # (All existing input handling logic goes here)
                        pass


            # --- Display & State Logic ---
            if dirty:
                # (Menu preparation logic remains the same)

                # --- Main Display Rendering ---
                current_page_name = main_pages[main_page_index]
                if last_run_analytics:
                    ui.display_run_analytics_screen(last_run_analytics)
                elif active_route or active_poi:
                    ui.display_navigation_screen(next_waypoint_info, is_main_page=False, active_route=active_route, gps_fix=gps_fix, poi_info=active_poi)
                elif wizard_state != 'IDLE':
                    # (Wizard menu rendering remains the same)
                    pass
                elif current_page_name == 'HOME':
                    ui.display_home_screen(speed_kph, alt_m, gps_fix, datetime.now().strftime("%H:%M"), recorder.is_recording(), incline_deg, show_last_lift_warning)
                elif current_page_name == 'COMPASS':
                    ui.display_compass_screen(heading, gps_fix)
                elif current_page_name == 'WEATHER':
                    latest_weather = weather_handler.get_latest_weather()
                    if weather_sub_page_index == 0: ui.display_current_weather_screen(latest_weather)
                    else: ui.display_snow_report_screen(latest_weather)
                elif current_page_name == 'STATS':
                    ui.display_summary_screen(db_manager.get_trip_summary())
                elif current_page_name == 'ACHIEVEMENTS':
                    bests = db_manager.get_days_bests()
                    ui.display_achievements_screen(bests)
                elif current_page_name == 'LOGBOOK':
                    log_entries = db_manager.get_run_log_entries()
                    total_pages = math.ceil(len(log_entries) / LOGBOOK_ITEMS_PER_PAGE) if log_entries else 0
                    start = logbook_page * LOGBOOK_ITEMS_PER_PAGE
                    paginated = log_entries[start : start + LOGBOOK_ITEMS_PER_PAGE]
                    for entry in paginated:
                        entry['time'] = datetime.fromisoformat(entry['timestamp']).strftime('%H:%M')
                    ui.display_run_logbook_screen(paginated, logbook_page + 1, total_pages)
                elif current_page_name == 'NAVIGATION':
                    ui.display_navigation_screen(None, is_main_page=True, gps_fix=gps_fix)
                elif current_page_name == 'DIRECTIONS':
                    ui.display_menu("Find Directions", [{'name': "Press 5 to start"}], page_indicator="DIRECTIONS")

                dirty = False
            time.sleep(0.02)
    finally:
        if recorder.is_recording(): recorder.stop()
        keypad.close()


