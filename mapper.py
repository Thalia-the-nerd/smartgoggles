import db_manager
from math import radians, sin, cos, sqrt, atan2
import heapq 
import time
import audio_handler
import random

# --- Configuration ---
PROXIMITY_RADIUS_METERS = 15 # Increased radius for better waypoint detection
EARTH_RADIUS_METERS = 6371000

# --- Helper Functions ---
def has_gps_data(point):
    if not isinstance(point, dict): return False
    lat, lon = point.get('lat'), point.get('lon')
    return isinstance(lat, (int, float)) and isinstance(lon, (int, float))

def haversine_distance(p1, p2):
    if not has_gps_data(p1) or not has_gps_data(p2):
        return float('inf') 
    lat1_rad, lon1_rad = radians(p1['lat']), radians(p1['lon'])
    lat2_rad, lon2_rad = radians(p2['lat']), radians(p2['lon'])
    dlon, dlat = lon2_rad - lon1_rad, lat2_rad - lat1_rad
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_METERS * c

# --- A* Pathfinding Algorithm (unchanged) ---
def a_star_search(nodes, graph, start_node_id, end_node_id):
    """
    Finds the shortest path from start_node_id to end_node_id using A* search.
    """
    open_set = [(0, start_node_id)] # (f_score, node_id)
    came_from = {}
    g_score = {node_id: float('inf') for node_id in nodes}
    g_score[start_node_id] = 0
    f_score = {node_id: float('inf') for node_id in nodes}
    f_score[start_node_id] = haversine_distance(nodes[start_node_id], nodes[end_node_id])
    
    while open_set:
        _, current_id = heapq.heappop(open_set)
        
        if current_id == end_node_id:
            # Reconstruct path
            path = []
            while current_id in came_from:
                path.append(nodes[current_id])
                current_id = came_from[current_id]
            path.append(nodes[start_node_id])
            return path[::-1] # Return reversed path (start to end)
            
        for neighbor_id, cost in graph.get(current_id, {}).items():
            tentative_g_score = g_score[current_id] + cost
            if tentative_g_score < g_score[neighbor_id]:
                came_from[neighbor_id] = current_id
                g_score[neighbor_id] = tentative_g_score
                f_score[neighbor_id] = tentative_g_score + haversine_distance(nodes[neighbor_id], nodes[end_node_id])
                heapq.heappush(open_set, (f_score[neighbor_id], neighbor_id))
    
    return None # No path found

# --- Main Mapper Functions ---
def build_resort_graph(difficulty_filter):
    """
    Builds the graph of all waypoints and the connections (runs/lifts)
    between them, filtered by the selected difficulty.
    """
    print(f"MAPPER_GRAPH: Building graph for difficulty: '{difficulty_filter}'")
    all_waypoints = db_manager.get_all_waypoints()
    all_runs = db_manager.get_all_runs_structured() 
    
    nodes = {wp['id']: wp for wp in all_waypoints}
    graph = {wp['id']: {} for wp in all_waypoints}
    
    difficulty_map = {'Green': 1, 'Blue': 2, 'Black': 3, 'Lift': 0}
    max_difficulty = difficulty_map.get(difficulty_filter, 1)
    print(f"MAPPER_GRAPH: Max difficulty value set to: {max_difficulty}")

    runs_processed = 0
    runs_skipped = 0

    for run in all_runs:
        run_difficulty_val = difficulty_map.get(run.get('difficulty'), 4)
        run_type = run.get('type')
        
        # Skip this run if it's harder than the user's selected difficulty
        # Lifts (difficulty 0) are always allowed
        if run_difficulty_val > max_difficulty and run_type == 'Run':
            print(f"MAPPER_GRAPH: Skipping run '{run.get('name')}' ({run.get('difficulty')}) - exceeds '{difficulty_filter}' difficulty.")
            runs_skipped += 1
            continue 
            
        runs_processed += 1
        waypoint_ids = run['waypoints_list']
        for i in range(len(waypoint_ids) - 1):
            start_node, end_node = nodes.get(waypoint_ids[i]), nodes.get(waypoint_ids[i+1])
            if start_node and end_node:
                cost = haversine_distance(start_node, end_node)
                # Add one-way connection (downhill)
                graph[start_node['id']][end_node['id']] = cost
                
                # If it's a lift, add a connection back (uphill)
                if run_type == 'Lift':
                    graph[end_node['id']][start_node['id']] = cost 
    
    print(f"MAPPER_GRAPH: Graph build complete. Processed {runs_processed} runs/lifts, skipped {runs_skipped} runs.")
    return nodes, graph

def check_path_existence(start_wp_id, dest_wp_id, difficulty):
    """
    (Used by web_manager)
    Quickly checks if a path of any kind exists.
    """
    nodes, graph = build_resort_graph(difficulty)
    if start_wp_id not in nodes or dest_wp_id not in nodes:
        return False
    return a_star_search(nodes, graph, start_wp_id, dest_wp_id) is not None

def find_n_closest_waypoints(current_location, n=5):
    """
    Finds the 'n' waypoints closest to the user's current location.
    """
    all_waypoints = db_manager.get_all_waypoints()
    if not all_waypoints or not has_gps_data(current_location):
        return []
        
    for wp in all_waypoints:
        wp['distance'] = haversine_distance(current_location, wp)
        
    return sorted(all_waypoints, key=lambda x: x['distance'])[:n]

# --- NEW FUNCTION TO FIX CRASH ---
def find_closest_poi(current_location, poi_type):
    """
    Finds the single closest waypoint of a specific type (e.g., 'Lodge').
    """
    all_waypoints = db_manager.get_all_waypoints()
    if not all_waypoints or not has_gps_data(current_location):
        return None
    
    # Filter waypoints by the requested POI type
    poi_waypoints = [wp for wp in all_waypoints if wp.get('type') == poi_type]
    if not poi_waypoints:
        print(f"MAPPER_WARN: No POIs of type '{poi_type}' found in database.")
        return None

    # Calculate distance for each POI
    for wp in poi_waypoints:
        wp['distance_m'] = haversine_distance(current_location, wp)
        
    # Return the one with the minimum distance
    closest = min(poi_waypoints, key=lambda x: x['distance_m'])
    print(f"MAPPER: Closest POI for '{poi_type}' is '{closest['name']}' at {closest['distance_m']:.0f}m")
    return closest
# --- END NEW FUNCTION ---

# --- MODIFIED FUNCTION TO ADD FALLBACK LOGIC ---
def find_smart_route_to_waypoint(start_waypoint_id, dest_wp_id, difficulty):
    """
    Finds the best path from a start waypoint to a destination waypoint
    at a given difficulty.
    
    If no path is found, it will try again with a harder difficulty
    and return a 'fallback_available' message.
    """
    print(f"MAPPER: Finding route from {start_waypoint_id} to {dest_wp_id} (Difficulty: {difficulty})")
    
    # 1. Build the graph for the selected difficulty
    nodes, graph = build_resort_graph(difficulty)
    
    if start_waypoint_id not in nodes:
        print(f"MAPPER_ERROR: Start waypoint ID {start_waypoint_id} not in nodes.")
        return None
    if dest_wp_id not in nodes:
        print(f"MAPPER_ERROR: Destination waypoint ID {dest_wp_id} not in nodes.")
        return None
        
    # 2. Call the A* search algorithm
    path_waypoints = a_star_search(nodes, graph, start_waypoint_id, dest_wp_id)
    
    # 3. If a path is found, return it
    if path_waypoints:
        print(f"MAPPER: Path found with {len(path_waypoints)} waypoints at '{difficulty}' difficulty.")
        # Save this route as the "last route" for the reverse function
        db_manager.save_last_navigation_route(path_waypoints)
        
        return {
            'waypoints': path_waypoints, 
            'current_wp_index': 0,
            'is_smart_route': True,
            'runs_in_route': [], 
            'run_log_data': [],
            'current_run_log_index': 0
        }
    
    # 4. --- NEW: Fallback Logic ---
    # If no path was found, try harder difficulties
    print(f"MAPPER_WARN: A* search returned no path for '{difficulty}'. Checking fallbacks...")

    if difficulty == 'Green':
        # Try Blue first
        if check_path_existence(start_waypoint_id, dest_wp_id, 'Blue'):
            print("MAPPER_INFO: No Green path, but a Blue path exists.")
            return {'fallback_available': 'Blue'}
        # If no Blue, try Black
        if check_path_existence(start_waypoint_id, dest_wp_id, 'Black'):
            print("MAPPER_INFO: No Green or Blue path, but a Black path exists.")
            return {'fallback_available': 'Black'}
            
    if difficulty == 'Blue':
        # Try Black
        if check_path_existence(start_waypoint_id, dest_wp_id, 'Black'):
            print("MAPPER_INFO: No Blue path, but a Black path exists.")
            return {'fallback_available': 'Black'}

    # 5. If no fallbacks are found, return None
    print("MAPPER_WARN: No path found at any difficulty.")
    return None
# --- END MODIFIED FUNCTION ---

def start_route(route_id, all_runs_by_id):
    """
    Starts a pre-defined route from the database.
    """
    route_details = db_manager.get_route_by_id(route_id)
    if not route_details or not route_details.get('runs_list'):
        return None
    
    initial_waypoints = db_manager.get_waypoints_for_route(route_id)
    if not initial_waypoints:
        return None
    
    # Save this as the "last route"
    db_manager.save_last_navigation_route(initial_waypoints)
    
    run_log_data = []
    for run_id in route_details.get('runs_list', []):
        run_info = all_runs_by_id.get(run_id)
        if run_info:
            run_log_data.append({
                'run_id': run_id,
                'run_name': run_info['name'],
                'start_time': None, 'end_time': None,
                'start_alt': None, 'end_alt': None,
                'points': []
            })

    return {
        'waypoints': initial_waypoints, 'current_wp_index': 0,
        'runs_in_route': route_details['runs_list'],
        'run_log_data': run_log_data,
        'current_run_log_index': 0
    }

def update_position(active_route, current_location):
    """
    Updates the user's position along the active route.
    Checks if they have reached the next waypoint.
    """
    if not active_route or not has_gps_data(current_location):
        return {'waypoint_info': get_current_waypoint_info(active_route)}

    if active_route['current_wp_index'] >= len(active_route['waypoints']):
        return None # Route is already finished
    
    # --- Analytics tracking for pre-defined routes ---
    current_run_log = None
    if 'run_log_data' in active_route and active_route.get('current_run_log_index', 0) < len(active_route.get('run_log_data', [])):
        current_run_log = active_route['run_log_data'][active_route['current_run_log_index']]
        if current_run_log['start_time'] is None:
            current_run_log['start_time'] = time.time()
            current_run_log['start_alt'] = current_location.get('alt_m')
        current_run_log['points'].append(current_location)
    # --- End analytics tracking ---

    next_wp = active_route['waypoints'][active_route['current_wp_index']]
    distance_to_wp = haversine_distance(current_location, next_wp)
    return_data = {}

    # --- Check for waypoint arrival ---
    if distance_to_wp < PROXIMITY_RADIUS_METERS:
        print(f"MAPPER: Arrived at waypoint {next_wp['name']}")
        active_route['current_wp_index'] += 1
        
        # --- Analytics finalization for pre-defined routes ---
        if current_run_log:
            run_info = db_manager.get_all_runs_structured() # Inefficient, better to pass this in
            run_info_map = {r['id']: r for r in run_info}
            current_run_definition = run_info_map.get(current_run_log['run_id'])
            
            if current_run_definition and next_wp['id'] == current_run_definition['waypoints_list'][-1]:
                current_run_log['end_time'] = time.time()
                current_run_log['end_alt'] = current_location.get('alt_m')
                
                # Calculate Analytics
                analytics = {
                    'run_name': current_run_log['run_name'],
                    'duration_seconds': current_run_log['end_time'] - current_run_log['start_time'],
                    'vertical_m': (current_run_log['start_alt'] - current_run_log['end_alt']) if current_run_log['start_alt'] and current_run_log['end_alt'] else 0,
                    'top_speed_kph': max(p.get('speed_kph', 0) for p in current_run_log['points']) if current_run_log['points'] else 0
                }
                return_data['analytics'] = analytics
                db_manager.log_completed_run(analytics) # Log to daily DB
                
                active_route['current_run_log_index'] += 1
        # --- End analytics finalization ---

        # Check if the whole route is finished
        if active_route['current_wp_index'] >= len(active_route['waypoints']):
            audio_handler.speak("Route finished.")
            return None 

        # Not finished, so get the new next waypoint
        new_next_wp = active_route['waypoints'][active_route['current_wp_index']]
        audio_handler.speak(f"Next, {new_next_wp['name']}")
        distance_to_wp = haversine_distance(current_location, new_next_wp)
        next_wp = new_next_wp

    return_data['waypoint_info'] = {'name': next_wp['name'], 'distance_m': distance_to_wp}
    return return_data

def get_current_waypoint_info(active_route):
    """
    Gets the name of the next waypoint (for display before GPS is ready).
    """
    if not active_route or active_route['current_wp_index'] >= len(active_route['waypoints']):
        return None
    next_wp = active_route['waypoints'][active_route['current_wp_index']]
    return {'name': next_wp['name']}

def reverse_route(active_route):
    """
    Takes an active route object and returns a new route object with the
    waypoint list reversed.
    """
    if not active_route or 'waypoints' not in active_route or not active_route['waypoints']:
        print("MAPPER: Cannot reverse an empty or invalid route.")
        return None

    print("MAPPER: Reversing the current route.")
    
    # Get the waypoints from the "last route" object saved in the DB
    last_route_waypoints = db_manager.get_last_navigation_route()
    if not last_route_waypoints:
        print("MAPPER_ERROR: Could not retrieve last route from DB to reverse.")
        return None
        
    reversed_waypoints = last_route_waypoints[::-1]
    
    # Save this new reversed route as the "last route"
    db_manager.save_last_navigation_route(reversed_waypoints)
    
    reversed_route_obj = {
        'waypoints': reversed_waypoints,
        'current_wp_index': 0,
        'is_smart_route': True,
        'runs_in_route': [],
        'run_log_data': [],
        'current_run_log_index': 0
    }
    
    print(f"MAPPER: New route created from '{reversed_waypoints[0]['name']}' to '{reversed_waypoints[-1]['name']}'.")
    return reversed_route_obj


