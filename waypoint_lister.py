import db_manager
import os

def list_all_waypoints():
    """
    Connects to the database and prints a formatted list of all
    waypoints, their IDs, and their types (like POIs).
    """
    
    # Check if the database file exists first
    if not os.path.exists(db_manager.DB_FILE):
        print(f"Error: Database file not found at '{db_manager.DB_FILE}'")
        print("Please run importdb.py first to create the database.")
        return

    print("--- Smart Goggles Waypoint & POI List ---")
    
    try:
        all_waypoints = db_manager.get_all_waypoints()
        
        if not all_waypoints:
            print("\nDatabase is empty. No waypoints found.")
            return

        # Separate POIs from standard junctions for clearer printing
        junctions = []
        pois = []

        for wp in all_waypoints:
            wp_type = wp.get('type', 'junction') # Get the type, default to 'junction'
            if wp_type and wp_type != 'junction':
                pois.append(wp)
            else:
                junctions.append(wp)

        # Print POIs first
        if pois:
            print("\n--- POIs (Points of Interest) ---")
            # Sort POIs by type, then name
            pois.sort(key=lambda x: (x.get('type', 'zz'), x['name']))
            for wp in pois:
                wp_type = wp.get('type', 'POI')
                print(f"  ID: {wp['id']:<5} | {wp['name']:<25} (Type: {wp_type})")
        
        # Print all other junctions
        if junctions:
            print("\n--- Junctions & Other Waypoints ---")
            # Sort junctions by ID
            junctions.sort(key=lambda x: x['id'])
            for wp in junctions:
                print(f"  ID: {wp['id']:<5} | {wp['name']:<25}")
                
        print("\n--- End of List ---")

    except Exception as e:
        print(f"\nAn error occurred while reading the database: {e}")

if __name__ == "__main__":
    list_all_waypoints()

