import db_manager
from math import radians, sin, cos, sqrt, atan2
import heapq 
import time
import audio_handler
import random # Import the random module

# --- Configuration ---
PROXIMITY_RADIUS_METERS = 10
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
    open_set = [(0, start_node_id)] 
    came_from = {}
    g_score = {node_id: float('inf') for node_id in nodes}
    g_score[start_node_id] = 0
    f_score = {node_id: float('inf') for node_id in nodes}
    f_score[start_node_id] = haversine_distance(nodes[start_node_id], nodes[end_node_id])
    while open_set:
        _, current_id = heapq.heappop(open_set)
        if current_id == end_node_id:
            path = []
            while current_id in came_from:
                path.append(nodes[current_id]); current_id = came_from[current_id]
            path.append(nodes[start_node_id]); return path[::-1]
        for neighbor_id, cost in graph.get(current_id, {}).items():
            tentative_g_score = g_score[current_id] + cost
            if tentative_g_score < g_score[neighbor_id]:
                came_from[neighbor_id] = current_id; g_score[neighbor_id] = tentative_g_score
                f_score[neighbor_id] = tentative_g_score + haversine_distance(nodes[neighbor_id], nodes[end_node_id])
                heapq.heappush(open_set, (f_score[neighbor_id], neighbor_id))
    return None

# --- Main Mapper Functions ---
def build_resort_graph(difficulty_filter):
    # ... (function content is unchanged) ...
    all_waypoints = db_manager.get_all_waypoints()
    all_runs = db_manager.get_all_runs_structured() 
    nodes = {wp['id']: wp for wp in all_waypoints}
    graph = {wp['id']: {} for wp in all_waypoints}
    difficulty_map = {'Green': 1, 'Blue': 2, 'Black': 3, 'Lift': 0}
    max_difficulty = difficulty_map.get(difficulty_filter, 1)
    for run in all_runs:
        run_difficulty = difficulty_map.get(run.get('difficulty'), 4)
        if run_difficulty > max_difficulty and run.get('type') == 'Run': continue
        waypoint_ids = run['waypoints_list']
        for i in range(len(waypoint_ids) - 1):
            start_node, end_node = nodes.get(waypoint_ids[i]), nodes.get(waypoint_ids[i+1])
            if start_node and end_node:
                cost = haversine_distance(start_node, end_node)
                graph[start_node['id']][end_node['id']] = cost
                if run.get('type') == 'Lift': graph[end_node['id']][start_node['id']] = cost 
    return nodes, graph

def check_path_existence(start_wp_id, dest_wp_id, difficulty):
    # ... (function content is unchanged) ...
    nodes, graph = build_resort_graph(difficulty)
    if start_wp_id not in nodes or dest_wp_id not in nodes: return False
    return a_star_search(nodes, graph, start_wp_id, dest_wp_id) is not None

def find_n_closest_waypoints(current_location, n=5):
    # ... (function content is unchanged) ...
    all_waypoints = db_manager.get_all_waypoints()
    if not all_waypoints or not has_gps_data(current_location): return []
    for wp in all_waypoints: wp['distance'] = haversine_distance(current_location, wp)
    return sorted(all_waypoints, key=lambda x: x['distance'])[:n]

def find_closest_poi(current_location, poi_type):
    """Finds the closest POI of a given type to the current location."""
    pois = db_manager.get_waypoints_by_type(poi_type)
    if not pois or not has_gps_data(current_location):
        return None
    
    closest_poi = min(pois, key=lambda poi: haversine_distance(current_location, poi))
    closest_poi['distance_m'] = haversine_distance(current_location, closest_poi)
    return closest_poi

def find_smart_route_to_waypoint(start_waypoint_id, dest_wp_id, difficulty):
    """
    Finds up to 5 distinct routes based on the first step and randomly returns one.
    """
    print(f"MAPPER: Finding multiple routes from WP ID {start_waypoint_id} to WP ID {dest_wp_id} with difficulty {difficulty}")
    nodes, graph = build_resort_graph(difficulty)

    if not nodes or start_waypoint_id not in nodes:
        return None

    # 1. Find all valid first steps (runs/lifts) from the start waypoint
    all_runs = db_manager.get_all_runs_structured()
    difficulty_map = {'Green': 1, 'Blue': 2, 'Black': 3, 'Lift': 0}
    max_difficulty_val = difficulty_map.get(difficulty, 1)
    
    potential_first_steps = []
    for run in all_runs:
        if run['waypoints_list'][0] == start_waypoint_id:
            run_difficulty_val = difficulty_map.get(run['difficulty'], 4)
            if run_difficulty_val <= max_difficulty_val or run['type'] == 'Lift':
                potential_first_steps.append(run)

    if not potential_first_steps:
        print("MAPPER: No valid starting runs found.")
        return None

    # 2. For each potential first step, find the optimal path from its end
    all_possible_routes = []
    for first_step_run in potential_first_steps:
        intermediate_start_wp_id = first_step_run['waypoints_list'][-1]
        
        if intermediate_start_wp_id == dest_wp_id:
            path_waypoints = [nodes[wp_id] for wp_id in first_step_run['waypoints_list']]
            all_possible_routes.append({'waypoints': path_waypoints, 'current_wp_index': 0})
            continue

        remaining_path = a_star_search(nodes, graph, intermediate_start_wp_id, dest_wp_id)
        
        if remaining_path:
            first_step_waypoints = [nodes[wp_id] for wp_id in first_step_run['waypoints_list']]
            full_path = first_step_waypoints + remaining_path[1:] # Avoid duplicating junction
            all_possible_routes.append({'waypoints': full_path, 'current_wp_index': 0})

    if not all_possible_routes:
        print("MAPPER: No complete paths found.")
        return None

    # 3. Limit to the top 5 (or fewer) distinct routes and randomly select one
    # To get more variety, we'll shuffle and pick from the first 5
    random.shuffle(all_possible_routes)
    top_routes = all_possible_routes[:5]
    print(f"MAPPER: Found {len(top_routes)} distinct route options. Randomly selecting one.")
    
    selected_route = random.choice(top_routes)
    selected_route['is_smart_route'] = True # Flag for other parts of the app
    
    print(f"MAPPER: Selected a route with {len(selected_route['waypoints'])} waypoints.")
    return selected_route

def start_route(route_id):
    # ... (function content is unchanged) ...
    route_details = db_manager.get_route_by_id(route_id)
    waypoints = db_manager.get_waypoints_for_route(route_id)
    if not waypoints or not route_details or not route_details.get('runs_list'): return None
    
    active_route = {
        'waypoints': waypoints, 'current_wp_index': 0,
        'runs_in_route': route_details['runs_list'],
        'current_run_index': 0, 
        'run_start_times': {}, # Use a dict to store start times per run_id
        'run_start_alt': {},   # Store starting altitude for analytics
        'run_log_data': {}     # Store trip log points per run_id
    }
    
    # Set the start time and altitude for the very first run
    first_run_id = route_details['runs_list'][0]
    active_route['run_start_times'][first_run_id] = time.time()
    # We'll get the starting altitude when the first GPS point comes in
    
    return active_route


def update_position(active_route, current_location):
    if not active_route or not has_gps_data(current_location):
        return get_current_waypoint_info(active_route)
    if active_route['current_wp_index'] >= len(active_route['waypoints']):
        return None

    # --- Analytics: Log current point to the active run ---
    if 'runs_in_route' in active_route:
        current_run_index = active_route.get('current_run_index', 0)
        if current_run_index < len(active_route['runs_in_route']):
            current_run_id = active_route['runs_in_route'][current_run_index]
            
            # Initialize log list for this run if it doesn't exist
            if current_run_id not in active_route['run_log_data']:
                active_route['run_log_data'][current_run_id] = []
            
            # Store starting altitude on the first data point for this run
            if current_run_id not in active_route['run_start_alt']:
                active_route['run_start_alt'][current_run_id] = current_location.get('alt_m')

            # Append current location data for analytics
            active_route['run_log_data'][current_run_id].append(current_location)

    # --- Waypoint Proximity Check ---
    next_wp = active_route['waypoints'][active_route['current_wp_index']]
    distance_to_wp = haversine_distance(current_location, next_wp)

    if distance_to_wp < PROXIMITY_RADIUS_METERS:
        # --- Handle Run Completion and Analytics ---
        if 'runs_in_route' in active_route:
            # Check if the waypoint we just reached is the end of a run
            all_runs = db_manager.get_all_runs_structured()
            for run in all_runs:
                if next_wp['id'] == run['waypoints_list'][-1] and run['id'] == active_route['runs_in_route'][active_route['current_run_index']]:
                    
                    # --- Calculate Analytics for the completed run ---
                    run_id = run['id']
                    start_time = active_route['run_start_times'].get(run_id)
                    
                    if start_time and run_id in active_route['run_log_data']:
                        duration = time.time() - start_time
                        
                        # Get analytics from the logged points for this run
                        logged_points = active_route['run_log_data'][run_id]
                        start_alt = active_route['run_start_alt'].get(run_id, 0)
                        end_alt = logged_points[-1].get('alt_m', start_alt)
                        vertical_m = start_alt - end_alt
                        top_speed_kph = max(p.get('speed_kph', 0) for p in logged_points) if logged_points else 0

                        # Add to logbook
                        db_manager.add_run_to_log(run_id, run['name'], duration, vertical_m, top_speed_kph)
                        print(f"ANALYTICS: Logged '{run['name']}'. Time: {duration:.1f}s, Vert: {vertical_m:.0f}m")

                        # Handle Ghost Race best time update
                        # (This logic can be expanded)

                    # --- Advance to the next run in the route ---
                    active_route['current_run_index'] += 1
                    if active_route['current_run_index'] < len(active_route['runs_in_route']):
                        next_run_id = active_route['runs_in_route'][active_route['current_run_index']]
                        active_route['run_start_times'][next_run_id] = time.time()

                    break # Exit the run check loop

        # --- Advance to the next waypoint ---
        active_route['current_wp_index'] += 1
        if active_route['current_wp_index'] >= len(active_route['waypoints']):
            audio_handler.speak("Route finished.")
            # Optionally, trigger a final summary screen here
            return None 
            
        new_next_wp = active_route['waypoints'][active_route['current_wp_index']]
        audio_handler.speak(f"Next, {new_next_wp['name']}")
        distance_to_wp = haversine_distance(current_location, new_next_wp)
        next_wp = new_next_wp

    return {'name': next_wp['name'], 'distance_m': distance_to_wp}


def get_current_waypoint_info(active_route):
    if not active_route or active_route['current_wp_index'] >= len(active_route['waypoints']):
        return None
    next_wp = active_route['waypoints'][active_route['current_wp_index']]
    return {'name': next_wp['name']}

