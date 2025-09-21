import db_manager
import mapper

def get_user_choice(prompt, options):
    """
    A helper function to display a numbered list and get a valid user choice.
    
    Args:
        prompt (str): The message to display to the user.
        options (list): A list of items for the user to choose from.
        
    Returns:
        The selected item from the list, or None if the choice is invalid.
    """
    print(f"\n--- {prompt} ---")
    if not options:
        print("No options available.")
        return None

    for i, option in enumerate(options):
        # Handle both dictionaries with a 'name' key and simple strings
        display_name = option.get('name') if isinstance(option, dict) else option
        print(f"{i + 1}. {display_name}")

    try:
        choice = int(input("> ")) - 1
        if 0 <= choice < len(options):
            return options[choice]
        else:
            print("Invalid number.")
            return None
    except ValueError:
        print("Invalid input. Please enter a number.")
        return None

def main():
    """
    Main function to run the command-line mapper test.
    """
    print("=============================")
    print(" SmartGoggles Mapper Test Tool ")
    print("=============================")

    # --- NEW: Print all existing data first ---
    print("\n--- Existing Database Data (Sorted) ---")

    all_waypoints = db_manager.get_all_waypoints()
    if all_waypoints:
        print("\n[Waypoints]")
        for wp in all_waypoints:
            print(f"- {wp['name']}")

    all_runs = db_manager.get_all_runs_structured()
    if all_runs:
        print("\n[Runs & Lifts]")
        for run in all_runs:
            print(f"- {run['name']} ({run['difficulty']})")

    all_routes = db_manager.get_all_routes_structured()
    if all_routes:
        print("\n[Routes]")
        for route in all_routes:
            print(f"- {route['name']} ({route['difficulty']})")
    
    print("\n---------------------------------")
    # --- End of new section ---

    # 1. Get all waypoints from the database (already fetched)
    if not all_waypoints:
        print("Error: No waypoints found in the database. Please run importdb.py first.")
        return

    # 2. Get the starting waypoint from the user
    start_waypoint = get_user_choice("Select a Starting Waypoint", all_waypoints)
    if not start_waypoint:
        return

    # 3. Get the destination waypoint from the user
    dest_waypoint = get_user_choice("Select a Destination Waypoint", all_waypoints)
    if not dest_waypoint:
        return
        
    if start_waypoint['id'] == dest_waypoint['id']:
        print("Start and destination cannot be the same.")
        return

    print("\nLOG: Checking for available path difficulties...")

    # 4. Check which difficulties have a valid path
    available_difficulties = []
    for diff in ['Green', 'Blue', 'Black']:
        if mapper.check_path_existence(start_waypoint['id'], dest_waypoint['id'], diff):
            available_difficulties.append(diff)
            print(f"LOG: Path found for '{diff}' difficulty.")
        else:
            print(f"LOG: No path found for '{diff}' difficulty.")

    if not available_difficulties:
        print("\nResult: No path of any difficulty could be found between these points.")
        return

    # 5. Get the desired difficulty from the user
    selected_difficulty = get_user_choice("Select an Available Difficulty", available_difficulties)
    if not selected_difficulty:
        return

    # 6. Find the final smart route
    print(f"\nLOG: Calculating '{selected_difficulty}' route from '{start_waypoint['name']}' to '{dest_waypoint['name']}'...")
    final_route = mapper.find_smart_route_to_waypoint(start_waypoint['id'], dest_waypoint['id'], selected_difficulty)

    # 7. Print the result
    print("\n--- RESULT ---")
    if final_route and final_route.get('waypoints'):
        print("Path found! The route is:")
        for i, waypoint in enumerate(final_route['waypoints']):
            print(f"  {i + 1}. {waypoint['name']}")
    else:
        print("No path could be found with the selected criteria.")
        
    print("\nTest complete.")

if __name__ == "__main__":
    main()

