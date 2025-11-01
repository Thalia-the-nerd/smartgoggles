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
import variables 
import audio_handler

# --- CONFIGURATION ---
KEYPAD_DEVICE_PATH = "/dev/input/by-id/usb-RDMCTMZT_Wireless_2.4G_Dongle_19971217-event-kbd"
ITEMS_PER_PAGE = 2 
LOGBOOK_ITEMS_PER_PAGE = 2
AUTO_RETURN_SECONDS = 10.0
ANALYTICS_DISPLAY_DURATION = 5.0

# Keybindings for ID entry
KEY_MAP = {
    79: '1', 80: '2', 81: '3', 75: '4', 76: '5', 77: '6',
    71: '7', 72: '8', 73: '9', 82: '0',
    96: 'ENTER',
    83: 'BACKSPACE',
    55: '*',
    55: 'BACK',
    82: 'SAVE_WAYPOINT',
    73: 'RECORD_TOGGLE',
}

def main(disp, gps_queue, gps_data, data_lock, ui):
    """
    Main application with improved responsiveness and fully implemented navigation.
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
    main_pages = ['HOME', 'COMPASS', 'PERFORMANCE', 'ACHIEVEMENTS', 'WEATHER', 'STATS', 'LOGBOOK', 'NAVIGATION', 'SKI PATROL', 'DIAGNOSTIC']
    main_page_index = 0
    
    weather_sub_page_index = 0
    sub_page_enter_time = 0
    logbook_page = 0
    menu_page = 0

    nav_state = 'IDLE' 
    nav_choices = {}
    id_input_buffer = ""
    menu_items = []

    active_route = None; next_waypoint_info = None;
    last_run_analytics = None; analytics_display_end_time = 0
    
    dirty = True 
    last_full_second_update = 0
    gps_data_cache = {}

    try:
        while True:
            current_time = time.time()
            if current_time - last_full_second_update >= 1.0:
                dirty = True; last_full_second_update = current_time

            # --- GPS Update ---
            try:
                while not gps_queue.empty():
                    new_gps_data = gps_queue.get_nowait()
                    gps_data_cache = new_gps_data.copy(); dirty = True
                with data_lock:
                    gps_data.update(gps_data_cache)
            except queue.Empty:
                pass
            
            current_location = {'lat': gps_data_cache.get('lat'), 'lon': gps_data_cache.get('lon'), 'alt_m': gps_data_cache.get('alt_m'), 'speed_kph': gps_data_cache.get('speed_kph', 0)}
            
            if active_route:
                update_result = mapper.update_position(active_route, current_location)
                if update_result:
                    if 'analytics' in update_result and update_result['analytics']:
                        last_run_analytics = update_result['analytics']; analytics_display_end_time = current_time + ANALYTICS_DISPLAY_DURATION
                    next_waypoint_info = update_result.get('waypoint_info')
                else: 
                    ui.display_message("Destination Reached", 2000); active_route = None
                dirty = True

            # --- Input Handling ---
            r, w, x = select.select([keypad], [], [], 0.01)
            if r:
                for event in keypad.read():
                    if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                        button = KEY_MAP.get(event.code)
                        if not button: continue
                        dirty = True

                        if button == 'BACK' or (nav_state in ['NAV_ENTER_POINT_ID', 'NAV_ENTER_START_ID'] and button == '*'):
                            if active_route: active_route = None
                            elif last_run_analytics: last_run_analytics = None
                            elif nav_state != 'IDLE': nav_state, nav_choices, menu_items, id_input_buffer = 'IDLE', {}, [], ""
                            continue

                        # --- Navigation State Machine ---
                        if nav_state != 'IDLE':
                            if nav_state == 'NAV_HUB':
                                if button == '1': nav_state = 'NAV_ENTER_POINT_ID'
                                elif button == '2': nav_state = 'NAV_SELECT_ROUTE_START'
                            
                            elif nav_state == 'NAV_ENTER_POINT_ID':
                                if button.isdigit(): id_input_buffer += button
                                elif button == 'BACKSPACE': id_input_buffer = id_input_buffer[:-1]
                                elif button == 'ENTER' and id_input_buffer:
                                    dest_wp = db_manager.get_waypoint_by_id(int(id_input_buffer))
                                    if dest_wp:
                                        nav_choices['dest_wp_id'] = dest_wp['id']
                                        nav_state = 'NAV_SELECT_POINT_START'
                                    else:
                                        ui.display_message("Invalid ID", 1500); id_input_buffer = ""
                            
                            elif nav_state == 'NAV_ENTER_START_ID': # New state for start ID
                                if button.isdigit(): id_input_buffer += button
                                elif button == 'BACKSPACE': id_input_buffer = id_input_buffer[:-1]
                                elif button == 'ENTER' and id_input_buffer:
                                    start_wp = db_manager.get_waypoint_by_id(int(id_input_buffer))
                                    if start_wp:
                                        nav_choices['start_wp_id'] = start_wp['id']
                                        nav_state = nav_choices.get('return_state', 'IDLE')
                                    else:
                                        ui.display_message("Invalid ID", 1500); id_input_buffer = ""

                            elif nav_state == 'NAV_SELECT_POINT_START' or nav_state == 'NAV_SELECT_ROUTE_START':
                                if button == '1': # Start from closest
                                    nav_choices['start_wp_id'] = menu_items[0]['wp_id']
                                    if nav_state == 'NAV_SELECT_POINT_START': nav_state = 'NAV_SELECT_DIFFICULTY'
                                    else: nav_state = 'NAV_SELECT_ROUTE'
                                elif button == '2': # Choose manually by ID
                                    if nav_state == 'NAV_SELECT_POINT_START':
                                        nav_choices['return_state'] = 'NAV_SELECT_DIFFICULTY'
                                    else:
                                        nav_choices['return_state'] = 'NAV_SELECT_ROUTE'
                                    nav_state = 'NAV_ENTER_START_ID'

                            elif nav_state == 'NAV_SELECT_ROUTE':
                                if button.isdigit() and 0 < int(button) <= len(menu_items):
                                    selected_route = menu_items[int(button) - 1]
                                    active_route = mapper.start_route_navigation(selected_route['route_id'])
                                    nav_state = 'IDLE'
                            
                            elif nav_state == 'NAV_SELECT_DIFFICULTY':
                                 if button.isdigit() and 0 < int(button) <= len(menu_items):
                                    selected_difficulty = menu_items[int(button) - 1]['difficulty']
                                    active_route = mapper.find_smart_route_to_waypoint(nav_choices['start_wp_id'], nav_choices['dest_wp_id'], selected_difficulty)
                                    if not active_route: ui.display_message("No Path Found", 1500)
                                    nav_state = 'IDLE'
                            
                            if nav_state == 'IDLE': # Reset menus if nav ended
                                menu_items, nav_choices, id_input_buffer = [], {}, ""
                            continue

                        # --- Main Page Input Logic ---
                        current_page_name = main_pages[main_page_index]
                        if button == '4': main_page_index = (main_page_index - 1 + len(main_pages)) % len(main_pages)
                        elif button == '6': main_page_index = (main_page_index + 1) % len(main_pages)
                        elif current_page_name == 'NAVIGATION' and not active_route:
                            nav_state = 'NAV_HUB'

            # --- Display Logic ---
            if dirty:
                header_data = {'gps_fix': gps_data_cache.get('fix', False), 'time_str': datetime.now().strftime("%H:%M:%S"), 'is_recording': recorder.is_recording()}

                if last_run_analytics:
                    ui.display_run_analytics_screen(last_run_analytics, header_data)
                elif active_route:
                    ui.display_navigation_screen(next_waypoint_info, header_data, is_main_page=False)
                elif nav_state != 'IDLE':
                    title = nav_state.replace('_', ' ').title()
                    
                    if nav_state == 'NAV_HUB':
                        menu_items = [{'name': '1. To Point'}, {'name': '2. Follow Route'}]
                        ui.display_menu("Navigation", menu_items, header_data)
                    
                    elif nav_state == 'NAV_ENTER_POINT_ID' or nav_state == 'NAV_ENTER_START_ID':
                        prompt = "Enter Dest ID" if nav_state == 'NAV_ENTER_POINT_ID' else "Enter Start ID"
                        wp = db_manager.get_waypoint_by_id(int(id_input_buffer)) if id_input_buffer else None
                        ui.display_id_entry_screen(prompt, id_input_buffer, wp['name'] if wp else "...", header_data)

                    elif nav_state in ['NAV_SELECT_POINT_START', 'NAV_SELECT_ROUTE_START']:
                        closest_wp = mapper.find_n_closest_waypoints(current_location, n=1)
                        if closest_wp and gps_data_cache.get('fix'):
                            menu_items = [{'name': f"1. At {closest_wp[0]['name']}", 'wp_id': closest_wp[0]['id']}, {'name': '2. By ID...'}]
                            ui.display_menu("Select Start", menu_items, header_data)
                        else:
                            ui.display_message("No GPS Signal", 1500); nav_state = 'IDLE'
                    
                    elif nav_state == 'NAV_SELECT_ROUTE':
                        routes = db_manager.get_routes_starting_at(nav_choices['start_wp_id'])
                        menu_items = [{'name': f"{i+1}. {r['name']}", 'route_id': r['id']} for i, r in enumerate(routes)]
                        ui.display_menu("Select Route", menu_items, header_data)

                    elif nav_state == 'NAV_SELECT_DIFFICULTY':
                        available = [d for d in ['Green', 'Blue', 'Black'] if mapper.check_path_existence(nav_choices['start_wp_id'], nav_choices['dest_wp_id'], d)]
                        if not available:
                            ui.display_message("No Path Found", 2000); nav_state = 'IDLE'
                        else:
                            menu_items = [{'name': f'{i+1}. {d}', 'difficulty': d} for i, d in enumerate(available)]
                            ui.display_menu("Select Difficulty", menu_items, header_data)

                else: # --- Main Page Rendering ---
                    current_page_name = main_pages[main_page_index]
                    if current_page_name == 'NAVIGATION':
                        ui.display_navigation_screen(None, header_data)
                    elif current_page_name == 'HOME':
                        ui.display_home_screen(gps_data_cache.get('speed_kph', 0), gps_data_cache.get('alt_m', 0), header_data)
                    elif current_page_name == 'SKI_PATROL':
                        ui.display_ski_patrol_screen(variables.SKI_PATROL_NUMBER, header_data)
                    # (Other pages rendered here)
                    elif current_page_name == 'COMPASS':
                        ui.display_compass_screen(gps_data_cache.get('heading', 0), header_data)
                    elif current_page_name == 'PERFORMANCE':
                        ui.display_performance_profile_screen(db_manager.get_performance_profile_from_log(), header_data)
                    elif current_page_name == 'ACHIEVEMENTS':
                        ui.display_achievements_screen(db_manager.get_days_bests(), header_data)
                    elif current_page_name == 'WEATHER':
                        latest_weather = weather_handler.get_latest_weather()
                        if weather_sub_page_index == 0: ui.display_current_weather_screen(latest_weather, header_data)
                        else: ui.display_snow_report_screen(latest_weather, header_data)
                    elif current_page_name == 'STATS':
                        ui.display_summary_screen(db_manager.get_todays_stats_from_daily_log(), header_data)
                    elif current_page_name == 'LOGBOOK':
                        log_entries = db_manager.get_run_log_entries()
                        start_index = logbook_page * LOGBOOK_ITEMS_PER_PAGE
                        paginated_entries = log_entries[start_index : start_index + LOGBOOK_ITEMS_PER_PAGE]
                        ui.display_run_logbook_screen(paginated_entries, header_data)
                    elif current_page_name == 'DIAGNOSTIC':
                        ui.display_diagnostic_screen(gps_data_cache, header_data)

                dirty = False
            time.sleep(0.01)
    finally:
        if recorder.is_recording(): recorder.stop()
        keypad.close()


