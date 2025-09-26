import db_manager
from math import radians, sin, cos, sqrt, atan2
import heapq 
import time
import audio_handler
import random

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
    nodes, graph = build_resort_graph(difficulty)
    if start_wp_id not in nodes or dest_wp_id not in nodes: return False
    return a_star_search(nodes, graph, start_wp_id, dest_wp_id) is not None

def find_n_closest_waypoints(current_location, n=5):
    all_waypoints = db_manager.get_all_waypoints()
    if not all_waypoints or not has_gps_data(current_location): return []
    for wp in all_waypoints: wp['distance'] = haversine_distance(current_location, wp)
    return sorted(all_waypoints, key=lambda x: x['distance'])[:n]

def find_closest_poi(current_location, poi_type):
    all_waypoints = db_manager.get_all_waypoints()
    if not all_waypoints or not has_gps_data(current_location): return None
    
    poi_waypoints = [wp for wp in all_waypoints if wp.get('type') == poi_type]
    if not poi_waypoints: return None

    for wp in poi_waypoints: wp['distance_m'] = haversine_distance(current_location, wp)
    return min(poi_waypoints, key=lambda x: x['distance_m'])

def find_smart_route_to_waypoint(start_waypoint_id, dest_wp_id, difficulty):
    print(f"MAPPER: Finding multiple routes from WP ID {start_waypoint_id} to WP ID {dest_wp_id} with difficulty {difficulty}")
    nodes, graph = build_resort_graph(difficulty)
    if not nodes or start_waypoint_id not in nodes: return None
    all_runs = db_manager.get_all_runs_structured()
    difficulty_map = {'Green': 1, 'Blue': 2, 'Black': 3, 'Lift': 0}
    max_difficulty_val = difficulty_map.get(difficulty, 1)
    potential_first_steps = []
    for run in all_runs:
        if run['waypoints_list'][0] == start_waypoint_id:
            run_difficulty_val = difficulty_map.get(run['difficulty'], 4)
            if run_difficulty_val <= max_difficulty_val or run['type'] == 'Lift':
                potential_first_steps.append(run)
    if not potential_first_steps: print("MAPPER: No valid starting runs found."); return None
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
            full_path = first_step_waypoints + remaining_path[1:]
            all_possible_routes.append({'waypoints': full_path, 'current_wp_index': 0})
    if not all_possible_routes: print("MAPPER: No complete paths found."); return None
    random.shuffle(all_possible_routes)
    top_routes = all_possible_routes[:5]
    selected_route = random.choice(top_routes)
    selected_route['is_smart_route'] = True
    return selected_route

def start_route(route_id, all_runs_by_id):
    route_details = db_manager.get_route_by_id(route_id)
    if not route_details or not route_details.get('runs_list'): return None
    
    initial_waypoints = db_manager.get_waypoints_for_route(route_id)
    if not initial_waypoints: return None
    
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
    if not active_route or not has_gps_data(current_location):
        return {'waypoint_info': get_current_waypoint_info(active_route)}

    if active_route['current_wp_index'] >= len(active_route['waypoints']):
        return None 
    
    current_run_log = None
    if 'run_log_data' in active_route and active_route['current_run_log_index'] < len(active_route['run_log_data']):
        current_run_log = active_route['run_log_data'][active_route['current_run_log_index']]
        if current_run_log['start_time'] is None:
            current_run_log['start_time'] = time.time()
            current_run_log['start_alt'] = current_location.get('alt_m')
        current_run_log['points'].append(current_location)

    next_wp = active_route['waypoints'][active_route['current_wp_index']]
    distance_to_wp = haversine_distance(current_location, next_wp)
    return_data = {}

    if distance_to_wp < PROXIMITY_RADIUS_METERS:
        active_route['current_wp_index'] += 1
        
        # Check if the just-completed waypoint was the end of a run
        if current_run_log:
            run_info = db_manager.get_all_runs_structured() # Inefficient, better to pass this in
            run_info_map = {r['id']: r for r in run_info}
            current_run_definition = run_info_map.get(current_run_log['run_id'])
            
            if current_run_definition and next_wp['id'] == current_run_definition['waypoints_list'][-1]:
                current_run_log['end_time'] = time.time()
                current_run_log['end_alt'] = current_location.get('alt_m')
                
                # --- Calculate Analytics ---
                analytics = {
                    'run_name': current_run_log['run_name'],
                    'duration_seconds': current_run_log['end_time'] - current_run_log['start_time'],
                    'vertical_m': (current_run_log['start_alt'] - current_run_log['end_alt']) if current_run_log['start_alt'] and current_run_log['end_alt'] else 0,
                    'top_speed_kph': max(p.get('speed_kph', 0) for p in current_run_log['points']) if current_run_log['points'] else 0
                }
                return_data['analytics'] = analytics
                db_manager.log_completed_run(analytics) # Log to daily DB
                
                active_route['current_run_log_index'] += 1

        if active_route['current_wp_index'] >= len(active_route['waypoints']):
            audio_handler.speak("Route finished.")
            return None 

        new_next_wp = active_route['waypoints'][active_route['current_wp_index']]
        audio_handler.speak(f"Next, {new_next_wp['name']}")
        distance_to_wp = haversine_distance(current_location, new_next_wp)
        next_wp = new_next_wp

    return_data['waypoint_info'] = {'name': next_wp['name'], 'distance_m': distance_to_wp}
    return return_data

def get_current_waypoint_info(active_route):
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
    
    reversed_waypoints = active_route['waypoints'][::-1]
    
    reversed_route_obj = {
        'waypoints': reversed_waypoints,
        'current_wp_index': 0,
        'is_smart_route': True,
        'is_ghost_race': False,
    }
    
    print(f"MAPPER: New route created from '{reversed_waypoints[0]['name']}' to '{reversed_waypoints[-1]['name']}'.")
    return reversed_route_obj


