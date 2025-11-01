import db_manager
import mapper

def get_user_choice(prompt, options):
    """A helper function to display a numbered list and get a valid user choice."""
    print(f"\n--- {prompt} ---")
    if not options:
        print("No options available.")
        return None

    for i, option in enumerate(options):
        print(f"{i + 1}. {option['name']}")

    raw_input = "" # Define outside the try block for use in the except block
    try:
        # Make input handling more robust by stripping whitespace.
        raw_input = input("> ")
        choice = int(raw_input.strip()) - 1 # .strip() removes leading/trailing spaces, tabs, newlines.
        if 0 <= choice < len(options):
            return options[choice]
        else:
            print("Invalid number.")
            return None
    except ValueError:
        # Add a more descriptive error message to help with debugging.
        print(f"Invalid input: '{raw_input}'. Please enter a number only.")
        return None

def main():
    """Main function to run the command-line directions tester."""
    print("=" * 30)
    print(" SmartGoggles Directions Tester ")
    print("=" * 30)

    all_waypoints = sorted(db_manager.get_all_waypoints(), key=lambda x: x['name'])
    all_runs = db_manager.get_all_runs_structured()

    if not all_waypoints or not all_runs:
        print("\nError: Database is missing waypoints or runs. Please run importdb.py first.")
        return

    # --- Get User Input ---
    start_waypoint = get_user_choice("Select a Starting Waypoint", all_waypoints)
    if not start_waypoint: return

    end_waypoint = get_user_choice("Select a Destination Waypoint", all_waypoints)
    if not end_waypoint: return

    if start_waypoint['id'] == end_waypoint['id']:
        print("\nError: Start and destination cannot be the same.")
        return

    print(f"\nSearching for all paths from '{start_waypoint['name']}' to '{end_waypoint['name']}'...")

    # --- Build a lookup map to convert waypoint pairs to run names ---
    run_lookup = {}
    for run in all_runs:
        for i in range(len(run['waypoints_list']) - 1):
            wp_pair = (run['waypoints_list'][i], run['waypoints_list'][i+1])
            run_name_with_diff = f"{run['name']} ({run['difficulty']})"
            run_lookup[wp_pair] = run_name_with_diff
            if run['type'] == 'Lift': # Lifts are bi-directional in the graph
                run_lookup[(wp_pair[1], wp_pair[0])] = run_name_with_diff
    
    # --- Test Each Difficulty ---
    any_path_found = False
    for diff in ['Green', 'Blue', 'Black']:
        print(f"\n--- Checking '{diff}' Difficulty Routes ---")
        
        nodes, graph = mapper.build_resort_graph(diff)
        
        # Find all possible first steps from the start node
        possible_first_steps = graph.get(start_waypoint['id'], {}).keys()
        
        found_routes_for_difficulty = set()

        for next_step_id in possible_first_steps:
            first_run_name = run_lookup.get((start_waypoint['id'], next_step_id), "Connector")
            
            # Find the rest of the path from the end of the first step
            remaining_path = mapper.a_star_search(nodes, graph, next_step_id, end_waypoint['id'])
            
            if remaining_path:
                any_path_found = True
                
                # Reconstruct the full path in run names
                full_path_names = [first_run_name]
                for i in range(len(remaining_path) - 1):
                    path_pair = (remaining_path[i]['id'], remaining_path[i+1]['id'])
                    run_name = run_lookup.get(path_pair, "Connector")
                    # Avoid adding duplicate consecutive run names (e.g., long runs)
                    if not full_path_names or full_path_names[-1] != run_name:
                        full_path_names.append(run_name)
                
                # Use a tuple for the set to ensure it's hashable
                found_routes_for_difficulty.add(tuple(full_path_names))

        if found_routes_for_difficulty:
            for i, route_tuple in enumerate(sorted(list(found_routes_for_difficulty))):
                print(f"  {i+1}. {' -> '.join(route_tuple)}")
        else:
            print("  No routes found for this difficulty.")

    if not any_path_found:
        print("\nResult: No path of any difficulty could be found between these points.")

    print("\nTest complete.")

if __name__ == "__main__":
    main()


