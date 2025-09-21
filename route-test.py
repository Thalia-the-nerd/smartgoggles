import db_manager
import mapper

def get_user_choice(prompt, options):
    """
    A helper function to display a numbered list and get a valid user choice.
    """
    print(f"\n--- {prompt} ---")
    if not options:
        print("No options available.")
        return None

    # Use a copy to avoid modifying the original list if numbering is added
    display_options = list(options)
    for i, option in enumerate(display_options):
        display_name = option.get('name') if isinstance(option, dict) else option
        print(f"{i + 1}. {display_name}")

    try:
        choice = int(input("> ")) - 1
        if 0 <= choice < len(display_options):
            return display_options[choice]
        else:
            print("Invalid number.")
            return None
    except ValueError:
        print("Invalid input. Please enter a number.")
        return None

def main():
    """
    Main function to run the command-line route test.
    """
    print("=========================")
    print(" SmartGoggles Route Tester ")
    print("=========================")

    # 1. Get all data from the database once at the start
    all_waypoints = db_manager.get_all_waypoints()
    all_runs = db_manager.get_all_runs_structured()
    all_routes = db_manager.get_all_routes_structured()
    
    if not all_waypoints or not all_runs:
        print("\nError: Database is missing waypoints or runs. Please populate it first.")
        return

    # 2. Display all existing data for context
    print("\n--- Existing Database Data (Sorted) ---")
    print("\n[Waypoints]")
    for wp in sorted(all_waypoints, key=lambda x: x['name']):
        print(f"- {wp['name']}")
    
    print("\n[Runs & Lifts]")
    for run in sorted(all_runs, key=lambda x: x['name']):
        print(f"- {run['name']} ({run['difficulty']})")
        
    print("\n[Pre-defined Routes]")
    for route in sorted(all_routes, key=lambda x: x['name']):
        print(f"- {route['name']}")
    
    # Run the test in a loop until the user quits
    try:
        while True:
            print("\n---------------------------------")
            print("Starting new route test (Press Ctrl+C to exit)")

            # 3. Get start and end points from the user
            start_waypoint = get_user_choice("Select a Starting Waypoint by number", all_waypoints)
            if not start_waypoint:
                continue

            end_waypoint = get_user_choice("Select a Destination Waypoint by number", all_waypoints)
            if not end_waypoint:
                continue
                
            if start_waypoint['id'] == end_waypoint['id']:
                print("\nError: Start and destination cannot be the same.")
                continue

            print(f"\nSearching for routes from '{start_waypoint['name']}' to '{end_waypoint['name']}'...")

            # 4. Build a lookup dictionary to map waypoint pairs to run objects
            run_lookup = {}
            for run in all_runs:
                for i in range(len(run['waypoints_list']) - 1):
                    wp_pair = (run['waypoints_list'][i], run['waypoints_list'][i+1])
                    run_lookup[wp_pair] = run # Store the whole run object
                    if run['type'] == 'Lift':
                        run_lookup[(wp_pair[1], wp_pair[0])] = run

            # 5. Find and display all distinct paths for each difficulty
            print("\n--- Possible Routes Found ---")
            any_path_found = False
            all_unique_routes_found = set() # Master set to track all found routes

            for diff in ['Green', 'Blue', 'Black']:
                print(f"[{diff.upper()}]")
                
                unique_routes_found_this_difficulty = set()
                difficulty_map = {'Green': 1, 'Blue': 2, 'Black': 3, 'Lift': 0}
                max_difficulty_val = difficulty_map.get(diff, 1)
                
                # Find all valid runs/lifts that start at the chosen waypoint
                potential_first_steps = []
                for run in all_runs:
                    if run['waypoints_list'][0] == start_waypoint['id']:
                        run_difficulty_val = difficulty_map.get(run['difficulty'], 4)
                        if run_difficulty_val <= max_difficulty_val or run['type'] == 'Lift':
                            potential_first_steps.append(run)

                # For each possible first step, try to find a path from its end to the final destination
                for first_step_run in potential_first_steps:
                    intermediate_start_wp_id = first_step_run['waypoints_list'][-1]
                    
                    # Case 1: The first step is the entire route
                    if intermediate_start_wp_id == end_waypoint['id']:
                        path_str = f"{first_step_run['name']} ({first_step_run['difficulty']})"
                        if path_str not in all_unique_routes_found:
                            print(f"  - {path_str}")
                            unique_routes_found_this_difficulty.add(path_str)
                            all_unique_routes_found.add(path_str)
                        continue

                    # Case 2: Find the rest of the path from the intermediate point
                    remaining_path_obj = mapper.find_smart_route_to_waypoint(intermediate_start_wp_id, end_waypoint['id'], diff)
                    
                    if remaining_path_obj and remaining_path_obj.get('waypoints'):
                        remaining_waypoints = remaining_path_obj['waypoints']
                        path_run_names = [f"{first_step_run['name']} ({first_step_run['difficulty']})"]
                        
                        # Convert the remaining waypoints to run names
                        for i in range(len(remaining_waypoints) - 1):
                            wp_pair = (remaining_waypoints[i]['id'], remaining_waypoints[i+1]['id'])
                            run_obj = run_lookup.get(wp_pair)
                            if run_obj:
                                run_name_with_diff = f"{run_obj['name']} ({run_obj['difficulty']})"
                                if not path_run_names or path_run_names[-1] != run_name_with_diff:
                                    path_run_names.append(run_name_with_diff)
                        
                        full_path_str = " --> ".join(path_run_names)
                        
                        if full_path_str not in all_unique_routes_found:
                            print(f"  - {full_path_str}")
                            unique_routes_found_this_difficulty.add(full_path_str)
                            all_unique_routes_found.add(full_path_str)
                
                if unique_routes_found_this_difficulty:
                    any_path_found = True
                else:
                    print("  (No new routes found for this difficulty)")
                    
                print("") # Add a newline for spacing

            if not any_path_found:
                print("No routes could be found between the selected waypoints.")
                
            print("Test complete.")

    except KeyboardInterrupt:
        print("\n\nExiting Route Tester. Goodbye!")
        return # Exit the main function gracefully

if __name__ == "__main__":
    main()

