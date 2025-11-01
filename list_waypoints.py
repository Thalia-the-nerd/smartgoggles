import db_manager

def list_all_waypoints():
    """
    Connects to the database and prints a formatted list of all waypoints with their IDs.
    """
    print("--- Smart Goggles Waypoint ID List ---")
    try:
        all_waypoints = db_manager.get_all_waypoints()
        if not all_waypoints:
            print("No waypoints found in the database.")
            return

        # Sort by ID for consistent ordering
        sorted_waypoints = sorted(all_waypoints, key=lambda x: x['id'])

        for wp in sorted_waypoints:
            # {:<4} ensures the ID is padded to 4 spaces for clean alignment
            print(f"ID: {wp['id']:<4} - {wp['name']}")

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure your 'skidata.db' file is in the same directory.")

if __name__ == "__main__":
    list_all_waypoints()

