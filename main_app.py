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
# MusicPlayer import removed
import weather_handler

# --- CONFIGURATION ---
KEYPAD_DEVICE_PATH = "/dev/input/by-id/usb-SEMICO_USB_Keyboard-event-kbd"
ITEMS_PER_PAGE = 3
AUTO_SCROLL_DELAY = 3.0 # Seconds to wait before starting auto-scroll
AUTO_SCROLL_INTERVAL = 2.0 # Seconds between each page turn

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
    Main application loop, now without the music player feature.
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
    # player = MusicPlayer() removed
    
    # --- Application State ---
    # 'MUSIC' page removed from list
    main_pages = ['HOME', 'WEATHER', 'STATS', 'NAVIGATION', 'DIRECTIONS']
    main_page_index = 0
    
    weather_sub_page_index = 0
    # music_sub_page_index removed

    wizard_state = 'IDLE' 
    wizard_choices = {}   
    menu_items = []
    full_menu_items = []
    menu_page = 0

    active_route = None
    next_waypoint_info = None
    dirty = True 
    
    # Auto-scroll state
    auto_scroll_start_time = None
    last_auto_scroll_time = 0
    
    current_location, speed_kph, alt_m, gps_fix = {}, 0, 0, False
    all_runs_by_id = {run['id']: run for run in db_manager.get_all_runs_structured()}

    try:
        while True:
            # --- GPS Update via Queue ---
            try:
                new_gps_data = gps_queue.get_nowait()
                current_location = {'lat': new_gps_data.get('lat'), 'lon': new_gps_data.get('lon')}
                speed_kph = new_gps_data.get('speed_kph', 0)
                alt_m = new_gps_data.get('alt_m', 0)
                gps_fix = new_gps_data.get('fix', False)
                dirty = True
                with data_lock:
                    gps_data.update({
                        'fix': gps_fix, 'lat': current_location['lat'], 'lon': current_location['lon'],
                        'alt': alt_m, 'speed': new_gps_data.get('speed_mps', 0)
                    })
            except queue.Empty:
                pass

            # --- Auto-scroll Logic ---
            if wizard_state in ['SELECT_START_WAYPOINT', 'SELECT_DEST_WAYPOINT'] and auto_scroll_start_time is not None:
                current_time = time.time()
                if current_time - auto_scroll_start_time > AUTO_SCROLL_DELAY:
                    if current_time - last_auto_scroll_time > AUTO_SCROLL_INTERVAL:
                        total_pages = math.ceil(len(full_menu_items) / ITEMS_PER_PAGE)
                        if total_pages > 1:
                            menu_page = (menu_page + 1) % total_pages
                            dirty = True
                            last_auto_scroll_time = current_time
                            print(f"LOG: Auto-scrolling to page {menu_page + 1}/{total_pages}.")

            # --- Input Handling ---
            r, w, x = select.select([keypad], [], [], 0.05)
            if r:
                for event in keypad.read():
                    if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                        button = KEY_MAP.get(event.code)
                        if not button: continue
                        print(f"LOG: Keypad button pressed: {button}")
                        dirty = True
                        auto_scroll_start_time = None # Stop auto-scroll on any key press

                        current_page_name = main_pages[main_page_index]
                        
                        if button == 'SKIP_WAYPOINT' and active_route:
                            if active_route['current_wp_index'] < len(active_route['waypoints']) - 1:
                                active_route['current_wp_index'] += 1
                            continue

                        # Entire 'if current_page_name == 'MUSIC':' block removed
                        
                        if current_page_name == 'WEATHER':
                            if button == '8' or button == '2': weather_sub_page_index = 1 - weather_sub_page_index

                        if wizard_state == 'IDLE' and not active_route:
                            if button == '4': 
                                main_page_index = (main_page_index - 1 + len(main_pages)) % len(main_pages)
                                weather_sub_page_index = 0
                            elif button == '6':
                                main_page_index = (main_page_index + 1) % len(main_pages)
                                weather_sub_page_index = 0
                            elif button == 'RECORD_TOGGLE':
                                if recorder.is_recording(): recorder.stop()
                                else: recorder.start()
                            elif button == 'SAVE_WAYPOINT':
                                if gps_fix and current_location.get('lat'):
                                    wp_name = f"WP {datetime.now().strftime('%H:%M:%S')}"
                                    db_manager.add_waypoint(wp_name, current_location['lat'], current_location['lon'], alt_m)
                                    ui.display_message("Waypoint Saved!", 1500)
                                else: ui.display_message("No GPS Fix!", 1500)
                            elif button == 'BACK' and main_page_index != 0: 
                                main_page_index = 0
                                weather_sub_page_index = 0
                            elif current_page_name == 'DIRECTIONS' and button == '5':
                                 wizard_state = 'SELECT_TYPE'
                            continue
                        
                        if button == 'BACK':
                            if active_route: active_route, next_waypoint_info = None, None
                            elif wizard_state != 'IDLE': wizard_state, wizard_choices, menu_items, full_menu_items, menu_page = 'IDLE', {}, [], [], 0
                            continue
                        
                        if wizard_state in ['SELECT_START_WAYPOINT', 'SELECT_DEST_WAYPOINT']:
                            total_pages = math.ceil(len(full_menu_items) / ITEMS_PER_PAGE)
                            if button == '4': menu_page = (menu_page - 1 + total_pages) % total_pages
                            elif button == '6': menu_page = (menu_page + 1) % total_pages
                        
                        if wizard_state != 'IDLE' and button.isdigit():
                            selected_item = None
                            if wizard_state in ['SELECT_START_WAYPOINT', 'SELECT_DEST_WAYPOINT']:
                                selection_index_in_full_list = (menu_page * ITEMS_PER_PAGE) + (int(button) - 1)
                                if 0 <= selection_index_in_full_list < len(full_menu_items):
                                    selected_item = full_menu_items[selection_index_in_full_list]
                            else:
                                if 0 <= (int(button) - 1) < len(menu_items):
                                    selected_item = menu_items[int(button) - 1]

                            if selected_item:
                                print(f"LOG: User selected '{selected_item.get('name')}' from '{wizard_state}' menu.")
                                action = selected_item.get('action')
                                
                                if action in ['MANUAL_SELECT_START', 'CHOOSE_MANUALLY', 'AUTO_FIND_START', 'CONFIRM_YES', 'MANUAL_START_SELECTED']:
                                    auto_scroll_start_time = time.time(); last_auto_scroll_time = time.time()
                                    print("LOG: Auto-scroll timer started (3s delay).")
                                
                                if action == 'GOTO_AREA': wizard_state = 'SELECT_AREA'
                                elif action == 'GOTO_WAYPOINT': wizard_state = 'SELECT_START_TYPE'
                                elif action == 'AUTO_FIND_START':
                                    if gps_fix and current_location.get('lat'):
                                        wizard_state = 'CONFIRM_START_WAYPOINT'
                                        wizard_choices['closest_waypoints'] = mapper.find_n_closest_waypoints(current_location)
                                        wizard_choices['closest_wp_attempt'] = 0
                                    else:
                                        ui.display_message("No GPS Signal", 1500); wizard_state = 'SELECT_START_WAYPOINT'
                                elif action == 'MANUAL_SELECT_START': wizard_state = 'SELECT_START_WAYPOINT'
                                elif action == 'CONFIRM_YES':
                                    wizard_choices['start_wp_id'] = selected_item['wp_id']; wizard_state = 'SELECT_DEST_WAYPOINT'
                                elif action == 'CONFIRM_NO': wizard_choices['closest_wp_attempt'] += 1
                                elif action == 'CHOOSE_MANUALLY': wizard_state = 'SELECT_START_WAYPOINT'
                                elif action == 'MANUAL_START_SELECTED':
                                    wizard_choices['start_wp_id'] = selected_item['wp_id']; wizard_state = 'SELECT_DEST_WAYPOINT'
                                elif action == 'DEST_SELECTED':
                                    wizard_choices['dest_wp_id'] = selected_item['wp_id']; wizard_state = 'FILTERING_DIFFICULTY'
                                elif action == 'SELECT_DIFFICULTY':
                                    wizard_choices['difficulty'] = selected_item['difficulty']
                                    active_route = mapper.find_smart_route_to_waypoint(wizard_choices['start_wp_id'], wizard_choices['dest_wp_id'], wizard_choices['difficulty'])
                                    if active_route:
                                        active_route['is_ghost_race'] = False
                                    else: 
                                        ui.display_message("No Path Found", 2000)
                                    wizard_state = 'IDLE'

                                menu_items, full_menu_items, menu_page = [], [], 0

            # --- Update Recorder State ---
            if active_route:
                if 'runs_in_route' in active_route:
                    current_run_index = active_route.get('current_run_index', 0)
                    if current_run_index < len(active_route['runs_in_route']):
                        current_run_id = active_route['runs_in_route'][current_run_index]
                        current_run_name = all_runs_by_id.get(current_run_id, {}).get('name', 'N/A')
                        with recorder_data_lock: recorder_data['current_run_name'] = current_run_name
                else:
                    with recorder_data_lock: recorder_data['current_run_name'] = 'Smart Route'
            else:
                with recorder_data_lock: recorder_data['current_run_name'] = 'Freeride'

            # --- Ghost Race Logic ---
            if active_route and active_route.get('is_ghost_race'):
                current_run_index = active_route.get('current_run_index', 0)
                if current_run_index < len(active_route.get('runs_in_route', [])):
                    current_run_id = active_route['runs_in_route'][current_run_index]
                    personal_best = db_manager.get_personal_best(current_run_id)
                    if personal_best:
                        current_run_time = time.time() - active_route['current_run_start_time']
                        delta = current_run_time - personal_best
                        if 'ghost_deltas' not in active_route: active_route['ghost_deltas'] = {}
                        active_route['ghost_deltas'][current_run_id] = delta
                    dirty = True

            # --- Display & State Logic ---
            if dirty:
                # --- Prepare Menus ---
                if wizard_state == 'SELECT_TYPE' and not menu_items:
                    menu_items = [{'name': '1. By Area', 'action': 'GOTO_AREA'}, {'name': '2. To Waypoint', 'action': 'GOTO_WAYPOINT'}]
                elif wizard_state == 'SELECT_START_TYPE' and not menu_items:
                    menu_items = [{'name': '1. Auto-find Start', 'action': 'AUTO_FIND_START'}, {'name': '2. Select Manually', 'action': 'MANUAL_SELECT_START'}]
                elif wizard_state in ['SELECT_START_WAYPOINT', 'SELECT_DEST_WAYPOINT'] and not full_menu_items:
                    waypoints = db_manager.get_all_waypoints()
                    action_name = 'MANUAL_START_SELECTED' if wizard_state == 'SELECT_START_WAYPOINT' else 'DEST_SELECTED'
                    full_menu_items = [{'name': w['name'], 'wp_id': w['id'], 'action': action_name} for w in waypoints]
                elif wizard_state == 'CONFIRM_START_WAYPOINT':
                    attempt = wizard_choices.get('closest_wp_attempt', 0)
                    closest_wps = wizard_choices.get('closest_waypoints', [])
                    if attempt < len(closest_wps):
                        wp_to_confirm = closest_wps[attempt]
                        menu_items = [{'name': f"1. Yes (I'm here)", 'action': 'CONFIRM_YES', 'wp_id': wp_to_confirm['id']}, {'name': f"2. No (Next closest)", 'action': 'CONFIRM_NO'}, {'name': f"3. Choose manually", 'action': 'CHOOSE_MANUALLY'}]
                    else:
                        ui.display_message("No other points nearby", 1500); wizard_state = 'SELECT_START_WAYPOINT'
                elif wizard_state == 'FILTERING_DIFFICULTY':
                    available_difficulties = []
                    for diff in ['Green', 'Blue', 'Black']:
                        if mapper.check_path_existence(wizard_choices['start_wp_id'], wizard_choices['dest_wp_id'], diff):
                            available_difficulties.append(diff)
                    if not available_difficulties:
                        ui.display_message("No Path Found", 2000); wizard_state = 'IDLE'
                    else:
                        wizard_state = 'SELECT_WAYPOINT_DIFFICULTY'
                        menu_items = [{'name': f'{i+1}. {d}', 'difficulty': d, 'action': 'SELECT_DIFFICULTY'} for i, d in enumerate(available_difficulties)]
                
                # --- Main Display Rendering ---
                current_page_name = main_pages[main_page_index]
                if active_route:
                    next_waypoint_info = mapper.update_position(active_route, current_location)
                    ui.display_navigation_screen(next_waypoint_info, is_main_page=False, active_route=active_.pyroute, gps_fix=gps_fix)
                    if next_waypoint_info is None:
                        ui.display_message("Route Finished!", 2000); active_route = None
                
                elif wizard_state != 'IDLE':
                    title = wizard_state.replace('_', ' ').title()
                    
                    items_to_display = menu_items
                    if wizard_state in ['SELECT_START_WAYPOINT', 'SELECT_DEST_WAYPOINT']:
                        total_pages = math.ceil(len(full_menu_items) / ITEMS_PER_PAGE)
                        if total_pages > 1: title += f" ({menu_page + 1}/{total_pages})"
                        
                        start_index = menu_page * ITEMS_PER_PAGE; end_index = start_index + ITEMS_PER_PAGE
                        paginated_items = full_menu_items[start_index:end_index]
                        
                        items_to_display = []
                        for i, item in enumerate(paginated_items):
                            display_item = item.copy()
                            display_item['name'] = f"{i+1}. {item['name']}"
                            items_to_display.append(display_item)

                    ui.display_menu(title, items_to_display)
                    
                elif current_page_name == 'HOME':
                    time_str = datetime.now().strftime("%H:%M")
                    ui.display_home_screen(speed_kph, alt_m, gps_fix, time_str, recorder.is_recording())
                
                elif current_page_name == 'WEATHER':
                    latest_weather = weather_handler.get_latest_weather()
                    if weather_sub_page_index == 0: ui.display_current_weather_screen(latest_weather)
                    else: ui.display_snow_report_screen(latest_weather)
                elif current_page_name == 'STATS':
                    ui.display_summary_screen(db_manager.get_trip_summary())
                # 'elif current_page_name == 'MUSIC':' block removed
                elif current_page_name == 'NAVIGATION':
                    ui.display_navigation_screen(None, is_main_page=True, gps_fix=gps_fix)
                elif current_page_name == 'DIRECTIONS':
                    ui.display_menu("Find Directions", [{'name': "Press 5 to start wizard"}], page_indicator="DIRECTIONS")

                dirty = False
            
            time.sleep(0.02)
            
    finally:
        if recorder.is_recording(): recorder.stop()
        print("LOG: Cleaning up keypad resource.")
        keypad.close()

