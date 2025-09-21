import time
from enum import Enum
import RPi.GPIO as GPIO

# Import all the project modules
import db_manager
import mapper
from ui_manager import UIManager

# --- Button Configuration (using GPIO BCM pin numbers) ---
# This is a sample layout for a 4x3 keypad. Adjust to your wiring.
KEYPAD_ROWS = [6, 13, 19, 26] # R1, R2, R3, R4
KEYPAD_COLS = [12, 16, 20]    # C1, C2, C3
KEYPAD_MAP = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['*', '0', '#']
]

# --- State Management ---
# Using an Enum makes the state logic clean and readable.
class AppState(Enum):
    HOME = 1
    MAIN_MENU = 2
    SELECT_ROUTE_MENU = 3
    SELECT_DESTINATION_MENU = 4
    NAVIGATING = 5
    TRIP_SUMMARY = 6

class ButtonManager:
    """Manages reading input from a 4x3 matrix keypad."""
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        # Setup rows as outputs
        for row_pin in KEYPAD_ROWS:
            GPIO.setup(row_pin, GPIO.OUT)
            GPIO.output(row_pin, 1)
        # Setup columns as inputs with pull-up resistors
        for col_pin in KEYPAD_COLS:
            GPIO.setup(col_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def check_for_press(self):
        """Scans the keypad matrix for a single key press."""
        for r_idx, row_pin in enumerate(KEYPAD_ROWS):
            GPIO.output(row_pin, 0) # Drive the current row low
            for c_idx, col_pin in enumerate(KEYPAD_COLS):
                if GPIO.input(col_pin) == 0:
                    GPIO.output(row_pin, 1) # Reset the row
                    return KEYPAD_MAP[r_idx][c_idx]
            GPIO.output(row_pin, 1) # Reset the row
        return None # No key pressed

def main(oled, gps_data, data_lock):
    """
    The main application function. It contains the primary state machine and event loop.
    """
    # --- Initialization ---
    ui = UIManager(oled)
    buttons = ButtonManager()
    
    current_state = AppState.HOME
    menu_items = []
    menu_selected_index = 0
    
    nav_manager = mapper.NavigationManager()
    active_route_name = None

    print("MAIN_APP: Starting main application loop.")

    # --- Main Application Loop ---
    while True:
        button_pressed = buttons.check_for_press()

        if current_state == AppState.HOME:
            if button_pressed == '#': # '#' is Menu/Select
                current_state = AppState.MAIN_MENU
                menu_items = ["Select Route", "Smart Map", "Trip Summary", "Save Waypoint"]
                menu_selected_index = 0

        elif current_state in [AppState.MAIN_MENU, AppState.SELECT_ROUTE_MENU, AppState.SELECT_DESTINATION_MENU]:
            if button_pressed == '8': # '8' is Down
                menu_selected_index = (menu_selected_index + 1) % len(menu_items)
            elif button_pressed == '2': # '2' is Up
                menu_selected_index = (menu_selected_index - 1 + len(menu_items)) % len(menu_items)
            elif button_pressed == '*': # '*' is Back/Cancel
                if current_state == AppState.MAIN_MENU:
                    current_state = AppState.HOME
                else: # Go back to the main menu from a sub-menu
                    current_state = AppState.MAIN_MENU
                    menu_items = ["Select Route", "Smart Map", "Trip Summary", "Save Waypoint"]
                    menu_selected_index = 0
            elif button_pressed == '#': # '#' is Select
                if current_state == AppState.MAIN_MENU:
                    selected_option = menu_items[menu_selected_index]
                    if selected_option == "Select Route":
                        current_state = AppState.SELECT_ROUTE_MENU
                        menu_items = db_manager.get_all_route_names()
                        menu_selected_index = 0
                    elif selected_option == "Smart Map":
                        current_state = AppState.SELECT_DESTINATION_MENU
                        menu_items = db_manager.get_all_waypoint_names()
                        menu_selected_index = 0
                    elif selected_option == "Trip Summary":
                        current_state = AppState.TRIP_SUMMARY
                    elif selected_option == "Save Waypoint":
                        # TODO: Implement waypoint saving
                        ui.display_message("Waypoint Saved!", duration_s=2)
                        current_state = AppState.HOME
                
                elif current_state == AppState.SELECT_ROUTE_MENU:
                    active_route_name = menu_items[menu_selected_index]
                    waypoint_sequence = db_manager.get_waypoints_for_route(active_route_name)
                    nav_manager.start_route(waypoint_sequence)
                    current_state = AppState.NAVIGATING

                elif current_state == AppState.SELECT_DESTINATION_MENU:
                    destination_waypoint_name = menu_items[menu_selected_index]
                    ui.display_message("Calculating...", duration_s=0)
                    # TODO: Implement smart route pathfinding in mapper.py
                    ui.display_message("Route Calculated!", duration_s=2)
                    current_state = AppState.NAVIGATING

        elif current_state == AppState.NAVIGATING:
            if button_pressed == '*': # '*' is Back/Cancel
                nav_manager.stop_route()
                current_state = AppState.HOME

            with data_lock:
                current_lat = gps_data.get('lat')
                current_lon = gps_data.get('lon')
            nav_manager.update_location(current_lat, current_lon)
            
        elif current_state == AppState.TRIP_SUMMARY:
            if button_pressed in ['*', '#']: # Back or Select returns home
                current_state = AppState.HOME

        # --- Draw the Screen Based on the New State ---
        if current_state == AppState.HOME:
            ui.display_home_screen(gps_data, data_lock)
        elif current_state == AppState.MAIN_MENU:
            ui.display_menu("Main Menu", menu_items, menu_selected_index)
        elif current_state == AppState.SELECT_ROUTE_MENU:
            ui.display_menu("Select Route", menu_items, menu_selected_index)
        elif current_state == AppState.SELECT_DESTINATION_MENU:
            ui.display_menu("Select Destination", menu_items, menu_selected_index)
        elif current_state == AppState.NAVIGATING:
            next_waypoint_info = nav_manager.get_next_waypoint_info()
            ui.display_navigation_screen(next_waypoint_info)
        elif current_state == AppState.TRIP_SUMMARY:
            summary_data = db_manager.get_trip_summary()
            ui.display_summary_screen(summary_data)
        
        time.sleep(0.1) # Debounce and prevent high CPU usage

