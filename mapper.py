import db_manager
from math import radians, sin, cos, sqrt, atan2, degrees
import heapq 
import time
import audio_handler

# --- Configuration ---
PROXIMITY_RADIUS_METERS = 15
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

# --- A* Pathfinding Logic (Restored) ---

def build_resort_graph(difficulty_filter):
    """Builds a graph of the resort's waypoints and connections for a given difficulty."""
    all_waypoints = db_manager.get_all_waypoints()
    all_runs = db_manager.get_all_runs_structured() 
    nodes = {wp['id']: wp for wp in all_waypoints}
    graph = {wp['id']: {} for wp in all_waypoints}
    
    difficulty_map = {'Green': 1, 'Blue': 2, 'Black': 3, 'Lift': 0}
    max_difficulty = difficulty_map.get(difficulty_filter, 1)

    for run in all_runs:
        run_difficulty_val = difficulty_map.get(run.get('difficulty'), 4)
        if run_difficulty_val > max_difficulty and run.get('type') == 'Run':
            continue
            
        waypoint_ids = run['waypoints_list']
        for i in range(len(waypoint_ids) - 1):
            start_node, end_node = nodes.get(waypoint_ids[i]), nodes.get(waypoint_ids[i+1])
            if start_node and end_node:
                cost = haversine_distance(start_node, end_node)
                graph[start_node['id']][end_node['id']] = cost
                if run.get('type') == 'Lift':
                    graph[end_node['id']][start_node['id']] = cost 
    return nodes, graph

def a_star_search(nodes, graph, start_node_id, end_node_id):
    """A* search algorithm to find the shortest path between two nodes."""
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
                path.append(nodes[current_id])
                current_id = came_from[current_id]
            path.append(nodes[start_node_id])
            return path[::-1]

        for neighbor_id, cost in graph.get(current_id, {}).items():
            tentative_g_score = g_score[current_id] + cost
            if tentative_g_score < g_score[neighbor_id]:
                came_from[neighbor_id] = current_id
                g_score[neighbor_id] = tentative_g_score
                f_score[neighbor_id] = tentative_g_score + haversine_distance(nodes[neighbor_id], nodes[end_node_id])
                heapq.heappush(open_set, (f_score[neighbor_id], neighbor_id))
    return None

# --- NEW Navigation Start Functions ---

def find_smart_route_to_waypoint(start_wp_id, dest_wp_id, difficulty):
    """Dynamically calculates a route to a waypoint using A* pathfinding."""
    nodes, graph = build_resort_graph(difficulty)
    if start_wp_id not in nodes or dest_wp_id not in nodes:
        return None
        
    path = a_star_search(nodes, graph, start_wp_id, dest_wp_id)
    if not path:
        return None
        
    return {
        'name': f"To {nodes[dest_wp_id]['name']}",
        'waypoints': path,
        'current_wp_index': 0,
    }

def start_route_navigation(route_id):
    """Creates a full route object from a predefined route ID."""
    # (This function remains the same as the last version)
    route_details = db_manager.get_route_by_id(route_id)
    waypoints = db_manager.get_waypoints_for_route(route_id)
    if not waypoints or not route_details or not route_details.get('runs_list'):
        return None
    all_runs_by_id = {run['id']: run for run in db_manager.get_all_runs_structured()}
    waypoint_to_run_map = {}
    for run_id in route_details['runs_list']:
        run_info = all_runs_by_id.get(run_id)
        if run_info:
            for i in range(len(run_info['waypoints_list']) - 1):
                start_wp_id = run_info['waypoints_list'][i]
                waypoint_to_run_map[start_wp_id] = run_id
    return {
        'id': route_id, 'name': route_details['name'],
        'waypoints': waypoints, 'current_wp_index': 0,
        'runs_in_route': route_details['runs_list'],
        'waypoint_to_run_map': waypoint_to_run_map,
        'current_run_id': None, 'current_run_start_time': None,
        'current_run_start_alt': None, 'current_run_max_speed': 0
    }

# --- Core Navigation Logic ---
def update_position(active_route, current_location):
    # (This function remains the same as the last version)
    if not active_route or not has_gps_data(current_location):
        return {'waypoint_info': get_current_waypoint_info(active_route)}
    if active_route['current_wp_index'] >= len(active_route['waypoints']):
        return None 
    if 'waypoint_to_run_map' in active_route:
        current_wp_id = active_route['waypoints'][active_route['current_wp_index']]['id']
        run_map = active_route.get('waypoint_to_run_map', {})
        if current_wp_id in run_map and run_map[current_wp_id] != active_route.get('current_run_id'):
            active_route['current_run_id'] = run_map[current_wp_id]
            active_route['current_run_start_time'] = time.time()
            active_route['current_run_start_alt'] = current_location.get('alt_m')
            active_route['current_run_max_speed'] = 0
        if active_route.get('current_run_id') is not None:
            current_speed = current_location.get('speed_kph', 0)
            if current_speed > active_route['current_run_max_speed']:
                active_route['current_run_max_speed'] = current_speed
    next_wp = active_route['waypoints'][active_route['current_wp_index']]
    distance_to_wp = haversine_distance(current_location, next_wp)
    if distance_to_wp < PROXIMITY_RADIUS_METERS:
        analytics_data = None
        if 'waypoint_to_run_map' in active_route and active_route.get('current_run_id') is not None:
            all_runs_by_id = {run['id']: run for run in db_manager.get_all_runs_structured()}
            finished_run_info = all_runs_by_id.get(active_route['current_run_id'])
            if finished_run_info and next_wp['id'] == finished_run_info['waypoints_list'][-1]:
                run_duration = time.time() - active_route['current_run_start_time']
                vertical_drop = active_route['current_run_start_alt'] - current_location.get('alt_m', 0) if active_route['current_run_start_alt'] else 0
                analytics_data = {'run_name': finished_run_info['name'], 'duration_seconds': run_duration, 'vertical_m': vertical_drop, 'top_speed_kph': active_route['current_run_max_speed']}
                db_manager.log_completed_run(analytics_data)
                pb = db_manager.get_personal_best(active_route['current_run_id'])
                if pb is None or run_duration < pb:
                    db_manager.update_personal_best(active_route['current_run_id'], run_duration)
                    analytics_data['personal_best'] = True
                active_route['current_run_id'] = None
        active_route['current_wp_index'] += 1
        if active_route['current_wp_index'] >= len(active_route['waypoints']):
            audio_handler.speak("Destination reached.")
            return None 
        new_next_wp = active_route['waypoints'][active_route['current_wp_index']]
        audio_handler.speak(f"Next, {new_next_wp['name']}")
        distance_to_wp = haversine_distance(current_location, new_next_wp)
        return {'waypoint_info': {'name': new_next_wp['name'], 'distance_m': distance_to_wp}, 'analytics': analytics_data}
    return {'waypoint_info': {'name': next_wp['name'], 'distance_m': distance_to_wp}}

def get_current_waypoint_info(active_route):
    # (This function remains the same)
    if not active_route or active_route['current_wp_index'] >= len(active_route['waypoints']):
        return None
    next_wp = active_route['waypoints'][active_route['current_wp_index']]
    return {'name': next_wp['name']}

def find_n_closest_waypoints(current_location, n=5):
    # (This function remains the same)
    all_waypoints = db_manager.get_all_waypoints()
    if not all_waypoints or not has_gps_data(current_location): return []
    for wp in all_waypoints: wp['distance'] = haversine_distance(current_location, wp)
    return sorted(all_waypoints, key=lambda x: x['distance'])[:n]

def check_path_existence(start_wp_id, dest_wp_id, difficulty):
    """Checks if a path exists between two waypoints for a given difficulty."""
    nodes, graph = build_resort_graph(difficulty)
    if start_wp_id not in nodes or dest_wp_id not in nodes:
        return False
    return a_star_search(nodes, graph, start_wp_id, dest_wp_id) is not None


