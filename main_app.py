import time
from datetime import datetime, timedelta
import evdev
import select
import queue
import threading
import math
import socket # For IP address
# import logging # REMOVED

# Import project modules
import db_manager
import mapper
from ui_manager import UIManager
from recorder import VideoRecorder
import weather_handler
import variables # Import the new variables file
import audio_handler

# --- CONFIGURATION ---
KEYPAD_DEVICE_PATH = "/dev/input/event5"

ITEMS_PER_PAGE = 2
LOGBOOK_ITEMS_PER_PAGE = 2
AUTO_SCROLL_DELAY = 3.0
AUTO_SCROLL_INTERVAL = 2.0
ANALYTICS_DISPLAY_DURATION = 5.0
AUTO_RETURN_SECONDS = 10.0 # Time before returning from a sub-page

# --- MODIFICATION: Updated KEY_MAP for numeric input ---
# Key mapping for a standard numeric keypad
KEY_MAP = {
    79: '1', 80: '2', 81: '3', 75: '4', 76: '5', 77: '6',
    71: '7', 72: '8', 73: '9', 82: '0', # 82 is KP_0
    55: 'BACK', # 55 is KP_Asterisk, used for Back/Cancel
    98: 'ENTER'  # 98 is KP_Slash, used for Confirm
}
# --- END MODIFICATION ---

# --- REMOVED Logging Setup ---

def _get_local_ip():
    """Tries to get the local IP address of the device."""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(('10.254.254.254', 1)) # Doesn't need to be reachable
        IP = s.getsockname()[0]
    except Exception:
        IP = None
    finally:
        if s:
            s.close()
    return IP

def main(disp, gps_queue, gps_data, data_lock, ui):
    """
    Main application with enhanced UI features.
    """
    # --- Initialization ---
    print("MAIN_APP: --- Main application starting up ---")
    try:
        keypad = evdev.InputDevice(KEYPAD_DEVICE_PATH)
        keypad.grab() # Grab the device to prevent its events from going to the OS
        print(f"MAIN_APP: Successfully grabbed keypad at {KEYPAD_DEVICE_PATH}")
    except FileNotFoundError:
        print(f"FATAL ERROR: Keypad not found at {KEYPAD_DEVICE_PATH}")
        return
    except IOError as e:
        print(f"FATAL ERROR: Could not grab keypad. Is script run with sudo? Error: {e}")
        return
        
    recorder_data = {}
    recorder_data_lock = threading.Lock()
    recorder = VideoRecorder(gps_queue, recorder_data, recorder_data_lock)
    
    print("MAIN_APP: Starting recorder automatically...")
    recorder.start()
    
    # --- NEW: Display IP Address ---
    local_ip = _get_local_ip()
    if local_ip:
        print(f"MAIN_APP: Local IP Found: {local_ip}")
        ui.display_message(f"IP: {local_ip}", 2000)
    else:
        print("MAIN_APP: No WiFi connection, skipping IP display.")
    # --- END NEW ---
    
    # --- Application State ---
    main_pages = ['HOME', 'COMPASS', 'ACHIEVEMENTS', 'WEATHER', 'STATS', 'LOGBOOK', 'NAVIGATION', 'DIRECTIONS']
    main_page_index = 0
    
    weather_sub_page_index = 0
    sub_page_enter_time = 0
    logbook_page = 0

    wizard_state = 'IDLE'; wizard_choices = {}; menu_items = []; full_menu_items = []; menu_page = 0
    
    input_buffer = ""
    
    active_route = None; next_waypoint_info = None; active_poi = None
    last_run_analytics = None; analytics_display_end_time = 0
    
    dirty = True 
    last_full_second_update = 0
    
    gps_data_cache = {}
    time_to_last_lift_seconds = None
    last_lift_warning_active = False
    
    all_waypoints_cache = {str(wp['id']): wp for wp in db_manager.get_all_waypoints()}
    print(f"MAIN_APP: Loaded {len(all_waypoints_cache)} waypoints into cache.")
    
    with recorder_data_lock:
        recorder_data['current_run_name'] = "N/A"

    try:
        while True:
            current_time = time.time()
            if current_time - last_full_second_update >= 1.0:
                dirty = True
                last_full_second_update = current_time

            # --- GPS Update & Position Tracking ---
            try:
                while not gps_queue.empty():
                    new_gps_data = gps_queue.get_nowait()
                    gps_data_cache = new_gps_data.copy()
                    with data_lock:
                        gps_data.update(new_gps_data)
                    dirty = True
            except queue.Empty:
                pass
            
            current_location = {'lat': gps_data_cache.get('lat'), 'lon': gps_data_cache.get('lon'), 'alt_m': gps_data_cache.get('alt_m')}
            speed_kph = gps_data_cache.get('speed_kph', 0)
            alt_m = gps_data_cache.get('alt_m', 0)
            gps_fix = gps_data_cache.get('fix', False)
            heading = gps_data_cache.get('heading', 0)
            incline_deg = gps_data_cache.get('incline_deg', 0)

            # --- Navigation & Run Tracking Logic ---
            current_run_name_for_overlay = "N/A"
            if active_route:
                update_result = mapper.update_position(active_route, current_location)
                if update_result:
                    if 'analytics' in update_result:
                        last_run_analytics = update_result['analytics']; analytics_display_end_time = current_time + ANALYTICS_DISPLAY_DURATION
                        print(f"NAV_INFO: Run analytics generated: {last_run_analytics}")
                    next_waypoint_info = update_result.get('waypoint_info')
                    
                    current_run_log_index = active_route.get('current_run_log_index', 0)
                    run_log_data = active_route.get('run_log_data', [])
                    if current_run_log_index < len(run_log_data):
                        current_run_name_for_overlay = run_log_data[current_run_log_index].get('run_name', 'N/A')
                    
                else: 
                    ui.display_message("Route Finished!", 2000); active_route = None; next_waypoint_info = None
                    print("NAV_INFO: Route finished.")
                    db_manager.clear_last_navigation_route() # Clear the last route
                dirty = True
            elif active_poi and gps_fix:
                active_poi['distance_m'] = mapper.haversine_distance(current_location, active_poi)
                current_run_name_for_overlay = f"-> {active_poi.get('name', 'POI')}"
                dirty = True
            
            with recorder_data_lock:
                 recorder_data['current_run_name'] = current_run_name_for_overlay

            if last_run_analytics and current_time > analytics_display_end_time:
                last_run_analytics = None; dirty = True

            if main_pages[main_page_index] == 'WEATHER' and weather_sub_page_index != 0:
                if current_time - sub_page_enter_time > AUTO_RETURN_SECONDS:
                    weather_sub_page_index = 0; dirty = True

            # --- Input Handling ---
            key_event = None
            try:
                key_event = keypad.read_one()
            except (IOError, evdev.errors.Errno19Error):
                print("FATAL ERROR: Keypad disconnected.")
                break 
            except BlockingIOError:
                pass
            
            if key_event and key_event.type == evdev.ecodes.EV_KEY and key_event.value == 1: # Key down
                button = KEY_MAP.get(key_event.code)
                
                if wizard_state in ['AWAIT_START_WP', 'AWAIT_END_WP']:
                    numeric_keys = {79: '1', 80: '2', 81: '3', 75: '4', 76: '5', 77: '6', 71: '7', 72: '8', 73: '9', 82: '0'}
                    if key_event.code in numeric_keys:
                        input_buffer += numeric_keys[key_event.code]
                        dirty = True
                    elif key_event.code == 55: # BACK key (Asterisk)
                        input_buffer = input_buffer[:-1] # Backspace
                        dirty = True
                    elif key_event.code == 98: # ENTER key (Slash)
                        if input_buffer: 
                            print(f"NAV_WIZARD: User entered ID: '{input_buffer}' for state {wizard_state}")
                            exact_match_wp = all_waypoints_cache.get(input_buffer)
                            
                            if exact_match_wp is None:
                                ui.display_message("No such ID", 1500)
                                print(f"NAV_WIZARD_WARN: ID Search Result: No such ID for '{input_buffer}'")
                                input_buffer = ""
                            
                            else: 
                                ui.display_message(f"Selected: {exact_match_wp['name']}", 1000)
                                print(f"NAV_WIZARD: ID Search Result: Found {exact_match_wp['name']} (ID: {exact_match_wp['id']})")
                                
                                if wizard_state == 'AWAIT_START_WP':
                                    wizard_choices['start_wp_id'] = exact_match_wp['id']
                                    wizard_state = 'SELECT_DESTINATION_TYPE'
                                    input_buffer = ""
                                elif wizard_state == 'AWAIT_END_WP':
                                    if wizard_choices.get('start_wp_id') == exact_match_wp['id']:
                                        ui.display_message("Cannot be same", 1500)
                                        print("NAV_WIZARD_WARN: User selected same Start and End WP ID.")
                                        input_buffer = ""
                                    else:
                                        wizard_choices['end_wp_id'] = exact_match_wp['id']
                                        wizard_state = 'SELECT_DIFFICULTY'
                                        input_buffer = ""
                            
                            dirty = True
                        
                    elif button == 'BACK' and not input_buffer: # Cancel / Exit
                         wizard_state = 'AWAIT_CLOSEST_OR_MANUAL'
                         print("NAV_WIZARD: User pressed Back from numeric input, returning to 'Use Closest' screen.")
                         dirty = True
                    continue 

                if not button:
                    continue
                
                dirty = True
                current_page_name = main_pages[main_page_index]
                
                # --- BACK Button Logic (Global) ---
                if button == 'BACK':
                    print("NAV_INFO: BACK button pressed.")
                    if active_route or active_poi: 
                        active_route, next_waypoint_info, active_poi = None, None, None
                        audio_handler.speak("Navigation cancelled.")
                        print("NAV_INFO: Active route/POI cancelled.")
                        db_manager.clear_last_navigation_route() # Clear reverse route
                    elif last_run_analytics: 
                        last_run_analytics = None
                        print("NAV_INFO: Analytics screen dismissed.")
                    elif wizard_state != 'IDLE':
                        print(f"NAV_WIZARD: Exiting wizard state {wizard_state}.")
                        if wizard_state in ['AWAIT_CLOSEST_OR_MANUAL', 'SELECT_DESTINATION_TYPE']:
                             wizard_state = 'SELECT_TYPE' # Go back to Nav Type
                        elif wizard_state in ['AWAIT_START_WP']:
                             wizard_state = 'AWAIT_CLOSEST_OR_MANUAL' # Go back to closest/manual
                        elif wizard_state in ['AWAIT_END_WP', 'SELECT_DIFFICULTY']:
                             wizard_state = 'SELECT_DESTINATION_TYPE' # Go back to Dest Type
                        # --- NEW: Go back from fallback confirm ---
                        elif wizard_state == 'CONFIRM_FALLBACK':
                             wizard_state = 'SELECT_DIFFICULTY' # Go back to difficulty select
                        # --- END NEW ---
                        else:
                             wizard_state = 'IDLE' # Default back
                        wizard_choices = {}; menu_items = []; full_menu_items = []; menu_page = 0; input_buffer = ""
                    elif main_page_index != 0:
                        main_page_index = 0
                        print("NAV_INFO: Returning to HOME screen.")
                    continue
                
                # --- Page-Specific Logic ---
                if current_page_name == 'LOGBOOK':
                    log_entries = db_manager.get_run_log_entries() 
                    total_pages = math.ceil(len(log_entries) / LOGBOOK_ITEMS_PER_PAGE) if log_entries else 0
                    if button == '2' and logbook_page > 0:
                        logbook_page -= 1
                    elif button == '8' and total_pages > 0 and logbook_page < total_pages - 1:
                        logbook_page += 1

                if current_page_name == 'WEATHER':
                    if button == '8' or button == '2':
                        weather_sub_page_index = 1 - weather_sub_page_index

                # --- Wizard / Menu Navigation ---
                if wizard_state != 'IDLE' and not active_route and not active_poi:
                    if button == '4': # Page Up
                        menu_page = max(0, menu_page - 1)
                    elif button == '6': # Page Down
                        total_pages = math.ceil(len(full_menu_items) / ITEMS_PER_PAGE)
                        menu_page = min(total_pages - 1, menu_page + 1)
                    elif button in ['1', '2', '3']:
                        selection_index = (menu_page * ITEMS_PER_PAGE) + (int(button) - 1)
                        if selection_index < len(full_menu_items):
                            selected_item = full_menu_items[selection_index]
                            print(f"NAV_WIZARD: User selected '{selected_item['name']}' from state {wizard_state}")
                            
                            if wizard_state == 'SELECT_TYPE':
                                wizard_choices['type'] = selected_item['name']
                                if selected_item['name'] == 'Pre-defined Route':
                                    wizard_state = 'SELECT_ROUTE'
                                elif selected_item['name'] == 'Nearest POI':
                                    wizard_state = 'SELECT_POI_TYPE'
                                elif selected_item['name'] == 'Waypoint-to-Waypoint':
                                    wizard_state = 'AWAIT_CLOSEST_OR_MANUAL'

                            elif wizard_state == 'AWAIT_CLOSEST_OR_MANUAL':
                                if selected_item['name'].startswith('Use Closest'):
                                    wizard_choices['start_wp_id'] = selected_item['id']
                                    wizard_state = 'SELECT_DESTINATION_TYPE'
                                elif selected_item['name'] == 'Enter ID Manually':
                                    wizard_state = 'AWAIT_START_WP'
                                    input_buffer = ""

                            elif wizard_state == 'SELECT_ROUTE':
                                wizard_choices['route_id'] = selected_item['id']
                                wizard_state = 'SELECT_DIFFICULTY'

                            elif wizard_state == 'SELECT_POI_TYPE':
                                wizard_choices['poi_type'] = selected_item['name']
                                if wizard_choices.get('type') == 'Nearest POI':
                                    wizard_state = 'IDLE'
                                    active_poi = mapper.find_closest_poi(current_location, wizard_choices['poi_type'])
                                    if active_poi: 
                                        audio_handler.speak(f"Navigating to {active_poi['name']}")
                                        print(f"NAV_WIZARD: Navigating to nearest POI: {active_poi['name']} (ID: {active_poi['id']})")
                                    else: 
                                        ui.display_message(f"No {wizard_choices['poi_type']} found", 2000)
                                        print(f"NAV_WIZARD_WARN: No POI found for type: {wizard_choices['poi_type']}")
                                elif wizard_choices.get('type') == 'Waypoint-to-Waypoint':
                                    wizard_state = 'SELECT_DIFFICULTY'
                            
                            elif wizard_state == 'SELECT_DESTINATION_TYPE':
                                if selected_item['name'] == 'To a Waypoint':
                                    wizard_state = 'AWAIT_END_WP'
                                    input_buffer = ""
                                elif selected_item['name'] == 'To Nearest POI':
                                    wizard_state = 'SELECT_POI_TYPE'
                            
                            # --- NEW: Handle Fallback Confirmation ---
                            elif wizard_state == 'CONFIRM_FALLBACK':
                                wizard_state = 'IDLE' # Exit wizard on selection
                                if selected_item['name'] == '1. Yes':
                                    print("NAV_WIZARD: User accepted fallback difficulty.")
                                    # Get all the stored choices
                                    start_wp_id = wizard_choices.get('start_wp_id')
                                    end_wp_id = wizard_choices.get('end_wp_id')
                                    new_diff = wizard_choices.get('fallback_difficulty')
                                    
                                    if start_wp_id and end_wp_id and new_diff:
                                        # Call mapper again, this time with the harder difficulty
                                        print(f"NAV_WIZARD: Finding W2W path: Start={start_wp_id}, End={end_wp_id}, Diff={new_diff}")
                                        active_route = mapper.find_smart_route_to_waypoint(start_wp_id, end_wp_id, new_diff)
                                        
                                    if not active_route or not active_route.get('waypoints'):
                                        ui.display_message("Error starting route", 2000)
                                        print(f"NAV_WIZARD_ERROR: Fallback route failed unexpectedly.")
                                        active_route = None
                                
                                elif selected_item['name'] == '2. No':
                                    print("NAV_WIZARD: User rejected fallback difficulty. Route cancelled.")
                                    ui.display_message("Route Cancelled", 1500)
                            # --- END NEW ---
                            
                            elif wizard_state == 'SELECT_DIFFICULTY':
                                wizard_choices['difficulty'] = selected_item['name']
                                wizard_state = 'IDLE' # We will exit wizard state unless a fallback is offered
                                
                                active_route = None # Ensure route is clear before starting
                                
                                if wizard_choices.get('type') == 'Pre-defined Route':
                                    all_runs_by_id = {run['id']: run for run in db_manager.get_all_runs_structured()}
                                    active_route = mapper.start_route(wizard_choices['route_id'], all_runs_by_id)
                                    print(f"NAV_WIZARD: Starting Pre-defined Route (ID: {wizard_choices['route_id']})")
                                
                                elif wizard_choices.get('type') == 'Waypoint-to-Waypoint':
                                    start_wp_id = wizard_choices.get('start_wp_id')
                                    difficulty = wizard_choices.get('difficulty')
                                    end_wp_id = None
                                    
                                    if 'end_wp_id' in wizard_choices:
                                        end_wp_id = wizard_choices['end_wp_id']
                                    elif 'poi_type' in wizard_choices:
                                        dest_poi = mapper.find_closest_poi(current_location, wizard_choices['poi_type'])
                                        if dest_poi:
                                            end_wp_id = dest_poi['id']
                                        else:
                                            ui.display_message(f"No {wizard_choices['poi_type']} found", 2000)
                                            print(f"NAV_WIZARD_WARN: Could not find POI '{wizard_choices['poi_type']}' to use as destination.")
                                    
                                    if start_wp_id and end_wp_id:
                                        if start_wp_id == end_wp_id:
                                            ui.display_message("Already at POI", 1500)
                                            print("NAV_WIZARD_INFO: Navigation cancelled: Start and End are the same.")
                                        else:
                                            print(f"NAV_WIZARD: Finding W2W path: Start={start_wp_id}, End={end_wp_id}, Diff={difficulty}")
                                            active_route = mapper.find_smart_route_to_waypoint(start_wp_id, end_wp_id, difficulty)
                                    
                                    elif not end_wp_id and 'poi_type' in wizard_choices:
                                        pass # Error was already displayed
                                    else:
                                        ui.display_message("Invalid Route", 2000)
                                        print(f"NAV_WIZARD_ERROR: Invalid route parameters: {wizard_choices}")

                                # --- NEW: Handle Fallback Response ---
                                if active_route and 'fallback_available' in active_route:
                                    new_diff = active_route['fallback_available']
                                    print(f"NAV_WIZARD: No path found at '{difficulty}'. Offering fallback to '{new_diff}'.")
                                    wizard_choices['fallback_difficulty'] = new_diff
                                    wizard_state = 'CONFIRM_FALLBACK' # Go to new confirmation screen
                                    active_route = None # Clear this so nav doesn't start
                                # --- END NEW ---

                                elif active_route and active_route.get('waypoints'):
                                    first_wp_name = active_route['waypoints'][0].get('name', 'first waypoint')
                                    audio_handler.speak(f"Route started. Proceed to {first_wp_name}")
                                    print(f"NAV_WIZARD: Path found. First step: {first_wp_name}")
                                    next_waypoint_info = mapper.get_current_waypoint_info(active_route)
                                
                                elif not active_route and not ('poi_type' in wizard_choices):
                                    ui.display_message("No Path Found", 2000)
                                    print("NAV_WIZARD_WARN: No path found for W2W route.")
                                    active_route = None
                            
                            menu_page = 0

                # --- Main Page Navigation (if not in wizard/route) ---
                elif wizard_state == 'IDLE' and not active_route and not active_poi:
                    if button == '4': # Left
                        main_page_index = (main_page_index - 1 + len(main_pages)) % len(main_pages)
                        weather_sub_page_index = 0; logbook_page = 0
                    elif button == '6': # Right
                        main_page_index = (main_page_index + 1) % len(main_pages)
                        weather_sub_page_index = 0; logbook_page = 0
                    
                    elif current_page_name == 'DIRECTIONS' and button == '5': 
                        wizard_state = 'SELECT_TYPE'
                        menu_page = 0
                        print("\nNAV_WIZARD: --- Navigation wizard started ---")
                    
                    elif current_page_name == 'NAVIGATION' and button == '5' and gps_fix:
                        last_route_waypoints = db_manager.get_last_navigation_route()
                        if last_route_waypoints:
                             print("NAV_INFO: Reversing last route.")
                             active_route = mapper.reverse_route({'waypoints': last_route_waypoints}) # Pass a simple route object
                        else:
                             ui.display_message("No route to reverse", 1500)
                             print("NAV_INFO: User tried to reverse route, but no last route was found.")

            # --- Display & State Logic ---
            if dirty:
                time_str = datetime.now().strftime("%H:%M")
                
                now = datetime.now()
                last_lift_dt = now.replace(hour=variables.LAST_LIFT_TIME[0], minute=variables.LAST_LIFT_TIME[1], second=0, microsecond=0)
                warning_30_min = last_lift_dt - timedelta(minutes=30)
                
                time_to_last_lift_seconds = None
                if now > warning_30_min and now < last_lift_dt:
                    time_to_last_lift_seconds = (last_lift_dt - now).total_seconds()
                    if not last_lift_warning_active:
                        audio_handler.speak("Lifts closing soon.")
                        print("AUDIO_WARN: Lifts closing soon.")
                        last_lift_warning_active = True
                elif now > last_lift_dt:
                    last_lift_warning_active = False

                # --- Prepare Menus (if in wizard) ---
                if wizard_state != 'IDLE':
                    
                    if wizard_state == 'AWAIT_START_WP' or wizard_state == 'AWAIT_END_WP':
                        display_name = ""
                        if input_buffer:
                            exact_match = all_waypoints_cache.get(input_buffer)
                            if exact_match:
                                display_name = f" ({exact_match['name']})"
                            else:
                                partial_matches = [wp['name'] for id_str, wp in all_waypoints_cache.items() if id_str.startswith(input_buffer)]
                                if len(partial_matches) == 0:
                                    display_name = " (No Match)"
                                elif len(partial_matches) == 1:
                                    display_name = f" ({partial_matches[0]})"
                                else:
                                    display_name = " (Multiple)"
                                    
                        full_menu_items = [{'name': input_buffer + '_' + display_name}]
                    
                    elif wizard_state == 'AWAIT_CLOSEST_OR_MANUAL':
                        if not gps_fix:
                            full_menu_items = [{'name': 'Waiting for GPS Fix...'}]
                        else:
                            closest_wps = mapper.find_n_closest_waypoints(current_location, n=1)
                            if closest_wps:
                                closest_wp = closest_wps[0]
                                full_menu_items = [
                                    {'name': f"Use Closest: {closest_wp['name']}", 'id': closest_wp['id']},
                                    {'name': 'Enter ID Manually'}
                                ]
                                # print(f"NAV_WIZARD: Offering 'Use Closest': {closest_wp['name']} (ID: {closest_wp['id']})")
                            else:
                                full_menu_items = [{'name': 'Enter ID Manually'}]
                                print("NAV_WIZARD: No closest waypoint found, offering manual entry only.")
                    
                    elif wizard_state == 'SELECT_TYPE':
                        full_menu_items = [
                            {'name': 'Pre-defined Route'}, 
                            {'name': 'Waypoint-to-Waypoint'},
                            {'name': 'Nearest POI'}
                        ]
                    elif wizard_state == 'SELECT_ROUTE':
                        if not gps_fix:
                            full_menu_items = [{'name': 'Waiting for GPS Fix...'}]
                        else:
                            all_routes = db_manager.get_all_routes_structured()
                            all_runs_by_id = {run['id']: run for run in db_manager.get_all_runs_structured()}
                            closest_wps = mapper.find_n_closest_waypoints(current_location, n=5)
                            if closest_wps:
                                closest_wps_ids = {wp['id'] for wp in closest_wps}
                                
                                possible_routes = []
                                for route in all_routes:
                                    if not route.get('runs_list'): continue
                                    first_run_id = route['runs_list'][0]
                                    first_run = all_runs_by_id.get(first_run_id)
                                    if not first_run or not first_run.get('waypoints_list'): continue
                                    start_wp_id = first_run['waypoints_list'][0]
                                    if start_wp_id in closest_wps_ids:
                                        possible_routes.append({'name': route['name'], 'id': route['id']})
                                full_menu_items = possible_routes
                                if not full_menu_items:
                                    full_menu_items = [{'name': 'No routes nearby...'}]
                                # print(f"NAV_WIZARD: Found {len(possible_routes)} nearby pre-defined routes.")
                            else:
                                full_menu_items = [{'name': 'No routes nearby...'}]
                                print("NAV_WIZARD: No closest waypoints found to filter pre-defined routes.")
                    
                    elif wizard_state == 'SELECT_POI_TYPE' or wizard_state == 'SELECT_END_POI_TYPE':
                        full_menu_items = [
                            {'name': 'Lodge'}, {'name': 'Restroom'}, {'name': 'Restaurant'}
                        ]
                    
                    elif wizard_state == 'SELECT_DESTINATION_TYPE':
                        full_menu_items = [
                            {'name': 'To a Waypoint'},
                            {'name': 'To Nearest POI'}
                        ]
                    
                    # --- NEW: Display for Fallback Confirmation ---
                    elif wizard_state == 'CONFIRM_FALLBACK':
                        fallback_diff = wizard_choices.get('fallback_difficulty', 'harder')
                        full_menu_items = [
                            {'name': f"Use {fallback_diff} path?"},
                            {'name': '1. Yes'},
                            {'name': '2. No'}
                        ]
                    # --- END NEW ---
                    
                    elif wizard_state == 'SELECT_DIFFICULTY':
                        full_to_list = wizard_choices.get('type') != 'Pre-defined Route'
                        full_menu_items = [
                            {'name': 'Green', 'desc': 'Easiest path'},
                            {'name': 'Blue', 'desc': 'Allow Blues'},
                            {'name': 'Black', 'desc': 'Allow All'}
                        ]
                        if not full_to_list:
                            full_menu_items = [{'name': 'Follow Route'}]

                    start = menu_page * ITEMS_PER_PAGE
                    menu_items = full_menu_items[start : start + ITEMS_PER_PAGE]

                # --- Render the Current Screen ---
                current_page_name = main_pages[main_page_index]
                if last_run_analytics:
                    ui.display_run_analytics_screen(last_run_analytics, gps_fix, time_str)
                elif active_route or active_poi:
                    ui.display_navigation_screen(next_waypoint_info, time_str, is_main_page=False, active_route=active_route, gps_fix=gps_fix, poi_info=active_poi)
                elif wizard_state != 'IDLE':
                    page_str = f"({menu_page + 1}/{math.ceil(len(full_menu_items) / ITEMS_PER_PAGE)})" if len(full_menu_items) > ITEMS_PER_PAGE else None
                    title_map = {
                        'SELECT_TYPE': 'SELECT NAV TYPE',
                        'SELECT_ROUTE': 'SELECT ROUTE',
                        'SELECT_POI_TYPE': 'SELECT POI TYPE',
                        'AWAIT_START_WP': 'Enter Start WP ID:',
                        'AWAIT_END_WP': 'Enter End WP ID:',
                        'AWAIT_CLOSEST_OR_MANUAL': 'SELECT START',
                        'SELECT_DESTINATION_TYPE': 'SELECT DEST TYPE',
                        'SELECT_END_POI_TYPE': 'SELECT POI TYPE',
                        'SELECT_DIFFICULTY': 'SELECT DIFFICULTY',
                        'CONFIRM_FALLBACK': f"NO {wizard_choices.get('difficulty','').upper()} PATH" # NEW
                    }
                    ui.display_menu(title_map.get(wizard_state, 'MENU'), menu_items, gps_fix, time_str, page_indicator=page_str)
                elif current_page_name == 'HOME':
                    ui.display_home_screen(speed_kph, alt_m, gps_fix, time_str, incline_deg, time_to_last_lift_seconds)
                elif current_page_name == 'COMPASS':
                    ui.display_compass_screen(heading, gps_fix, time_str)
                elif current_page_name == 'ACHIEVEMENTS':
                    ui.display_achievements_screen(db_manager.get_days_bests(), gps_fix, time_str)
                elif current_page_name == 'WEATHER':
                    latest_weather = weather_handler.get_latest_weather()
                    if weather_sub_page_index == 0: ui.display_current_weather_screen(latest_weather, gps_fix, time_str)
                    else: ui.display_snow_report_screen(latest_weather, gps_fix, time_str)
                elif current_page_name == 'STATS':
                    ui.display_summary_screen(db_manager.get_todays_stats_from_daily_log(), gps_fix, time_str)
                elif current_page_name == 'LOGBOOK':
                    log_entries = db_manager.get_run_log_entries()
                    total_pages = math.ceil(len(log_entries) / LOGBOOK_ITEMS_PER_PAGE) if log_entries else 0
                    start = logbook_page * LOGBOOK_ITEMS_PER_PAGE
                    paginated = log_entries[start : start + LOGBOOK_ITEMS_PER_PAGE]
                    # --- FIX: Corrected function name ---
                    ui.display_run_logbook_screen(paginated, logbook_page + 1, total_pages, gps_fix, time_str)
                    # --- END FIX ---
                elif current_page_name == 'NAVIGATION':
                    ui.display_navigation_screen(None, time_str, is_main_page=True, gps_fix=gps_fix)
                elif current_page_name == 'DIRECTIONS':
                    ui.display_menu("Find Directions", [{'name': "Press 5 to start"}], gps_fix, time_str, page_indicator="DIRECTIONS")

                dirty = False
            
            time.sleep(0.02)
            
    finally:
        print("MAIN_APP: --- Main application shutting down ---")
        if recorder.is_recording(): recorder.stop()
        keypad.ungrab()
        keypad.close()



