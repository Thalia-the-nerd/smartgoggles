from flask import Flask, render_template_string, request, redirect, url_for, flash
import db_manager
import mapper
import os
import sqlite3

# Ensure the database exists and is set up before the app starts
if not os.path.exists(db_manager.DB_FILE):
    print(f"WEB_MANAGER: Database not found at '{db_manager.DB_FILE}'. Creating now...")
    db_manager.setup_database()

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_for_flash_messages'

# --- THE ENTIRE WEB APPLICATION IS CONTAINED IN THIS TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartGoggles DB Manager</title>
    <style>
        :root { 
            --c-blue: #007bff; --c-gray: #f8f9fa; --c-dark: #343a40; 
            --c-light: #fff; --c-red: #dc3545; --c-green: #28a745; 
            --c-border: #dee2e6;
        }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; 
            background-color: var(--c-gray); margin: 0; padding: 1rem; color: var(--c-dark);
        }
        .container { max-width: 1400px; margin: auto; }
        h1, h2, h3 { border-bottom: 2px solid #e9ecef; padding-bottom: 0.5rem; margin-top: 2rem; }
        h3 { border: none; margin-top: 0; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 1.5rem; }
        .card { background: var(--c-light); border-radius: 0.5rem; padding: 1.5rem; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        label { font-weight: 600; display: block; margin-bottom: 0.5rem; }
        input, select { 
            width: calc(100% - 22px); padding: 0.6rem; margin-bottom: 1rem; 
            border: 1px solid var(--c-border); border-radius: 0.25rem; font-size: 1rem;
        }
        button, .btn { 
            padding: 0.6rem 1rem; border: none; border-radius: 0.25rem; cursor: pointer; 
            font-size: 1rem; font-weight: 600; text-decoration: none; display: inline-block; 
            color: var(--c-light) !important;
        }
        .btn-primary { background-color: var(--c-blue); }
        .btn-danger { background-color: var(--c-red); }
        .btn-secondary { background-color: #6c757d; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--c-border); vertical-align: top; }
        th { background-color: #e9ecef; }
        .actions form { margin-bottom: 0.5rem; }
        .flash { padding: 1rem; margin: 1rem 0; border-radius: 0.25rem; border: 1px solid transparent; }
        .flash-success { background-color: #d4edda; color: #155724; border-color: #c3e6cb; }
        .flash-danger { background-color: #f8d7da; color: #721c24; border-color: #f5c6cb; }
        
        details { margin-bottom: 1rem; }
        summary { cursor: pointer; font-weight: 600; color: var(--c-blue); }
        .selector-container { display: flex; gap: 1rem; margin-top: 0.5rem; margin-bottom: 1rem; }
        .selector-box { flex: 1; border: 1px solid var(--c-border); border-radius: 0.25rem; padding: 0.5rem; height: 200px; overflow-y: auto; }
        .selector-box strong { font-size: 0.9rem; color: #6c757d; }
        .selector-box ul { list-style-type: none; padding: 0; margin: 0.5rem 0 0 0; }
        .selector-box li { padding: 0.5rem; cursor: pointer; border-radius: 0.25rem; }
        .selector-box li:hover { background-color: #e9ecef; }
        .details-list { margin-top: 0.5rem; padding-left: 1.5rem; font-size: 0.9rem; }
    </style>
</head>
<body>
<div class="container">
    <h1>SmartGoggles Database Manager</h1>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}{% for category, message in messages %}
        <div class="flash flash-{{ category }}">{{ message|safe }}</div>
      {% endfor %}{% endif %}
    {% endwith %}

    <!-- Route Path Checker -->
    <div class="card">
        <h2>Route Path Checker</h2>
        <form action="{{ url_for('index') }}" method="post">
            <input type="hidden" name="action" value="check_route">
            <div class="grid">
                <div>
                    <label>Start Waypoint</label>
                    <select name="start_wp_id">
                        {% for wp in waypoints %}<option value="{{ wp.id }}">{{ wp.name }}</option>{% endfor %}
                    </select>
                </div>
                <div>
                    <label>End Waypoint</label>
                    <select name="end_wp_id">
                        {% for wp in waypoints %}<option value="{{ wp.id }}">{{ wp.name }}</option>{% endfor %}
                    </select>
                </div>
            </div>
            <button type="submit" class="btn btn-primary">Check for Paths</button>
        </form>
    </div>

    <!-- WAYPOINTS SECTION (RESTORED) -->
    <h2>Waypoints</h2>
    <div class="grid">
        <div class="card">
            <h3>Add Waypoint</h3>
            <form action="{{ url_for('index') }}" method="post">
                <input type="hidden" name="action" value="add_waypoint">
                <label>Name</label><input type="text" name="name" required>
                <details><summary>Set GPS Coordinates (Optional)</summary>
                    <label style="margin-top: 1rem;">Latitude</label><input type="number" step="any" name="lat" placeholder="e.g., 39.58">
                    <label>Longitude</label><input type="number" step="any" name="lon" placeholder="e.g., -106.17">
                </details>
                <button type="submit" class="btn btn-primary">Add Waypoint</button>
            </form>
        </div>
        <div class="card">
            <h3>Existing Waypoints</h3>
            <div style="overflow-x:auto;">
            <table>
                <thead><tr><th>Name</th><th>Actions</th></tr></thead>
                <tbody>
                {% for wp in waypoints %}
                    <tr>
                        <td>
                            <form action="{{ url_for('index') }}" method="post">
                                <input type="hidden" name="action" value="update_waypoint">
                                <input type="hidden" name="id" value="{{ wp.id }}">
                                <input type="text" name="name" value="{{ wp.name }}" required>
                                <details><summary>Edit GPS</summary>
                                    <input type="number" step="any" name="lat" value="{{ wp.lat or '' }}" placeholder="Latitude">
                                    <input type="number" step="any" name="lon" value="{{ wp.lon or '' }}" placeholder="Longitude">
                                </details>
                                <input type="hidden" name="alt" value="{{ wp.alt }}">
                        </td>
                        <td class="actions">
                                <button type="submit" class="btn btn-secondary">Update</button>
                            </form>
                            <form action="{{ url_for('index') }}" method="post" onsubmit="return confirm('Really delete {{ wp.name }}?');">
                                <input type="hidden" name="action" value="delete_waypoint">
                                <input type="hidden" name="id" value="{{ wp.id }}">
                                <button type="submit" class="btn btn-danger">Delete</button>
                            </form>
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            </div>
        </div>
    </div>

    <!-- RUNS/LIFTS SECTION -->
    <h2>Runs & Lifts</h2>
    <div class="grid">
        <div class="card">
            <h3>Add Run/Lift</h3>
            <form action="{{ url_for('index') }}" method="post" onsubmit="return consolidateOrder('selected_waypoints', 'run_waypoints_order');">
                 <input type="hidden" name="action" value="add_run">
                <input type="hidden" id="run_waypoints_order" name="waypoints_order">
                <label>Name</label><input type="text" name="name" required>
                <label>Type</label><select name="type"><option>Run</option><option>Lift</option></select>
                <label>Difficulty</label><select name="difficulty"><option>Green</option><option>Blue</option><option>Black</option><option>Lift</option></select>
                <label>Waypoints</label>
                <div class="selector-container">
                    <div class="selector-box"><strong>Available</strong><ul id="available_waypoints">
                    {% for wp in waypoints %}<li onclick="moveItem(this, 'selected_waypoints')">{{ wp.name }}<span class="item-id" style="display:none;">{{wp.id}}</span></li>{% endfor %}
                    </ul></div>
                    <div class="selector-box"><strong>Selected (in order)</strong><ul id="selected_waypoints" onclick="moveItemBack(event, 'available_waypoints')"></ul></div>
                </div>
                <button type="submit" class="btn btn-primary">Add Run/Lift</button>
            </form>
        </div>
        <div class="card">
            <h3>Existing Runs & Lifts</h3>
            <table>
                <thead><tr><th>Name</th><th>Type</th><th>Difficulty</th><th>Actions</th></tr></thead>
                <tbody>
                {% for run in runs %}
                    <tr>
                        <td>
                            <details><summary>{{ run.name }}</summary>
                                <ol class="details-list">
                                {% for wp_name in run.waypoint_names %}<li>{{ wp_name }}</li>{% endfor %}
                                </ol>
                            </details>
                        </td>
                        <td>{{ run.type }}</td>
                        <td>{{ run.difficulty }}</td>
                        <td class="actions">
                            <form action="{{ url_for('index') }}" method="post" onsubmit="return confirm('Really delete {{ run.name }}?');">
                                <input type="hidden" name="action" value="delete_run">
                                <input type="hidden" name="id" value="{{ run.id }}">
                                <button type="submit" class="btn btn-danger">Delete</button>
                            </form>
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <!-- ROUTES SECTION -->
    <h2>Routes</h2>
    <div class="grid">
        <div class="card">
            <h3>Add Route</h3>
            <form action="{{ url_for('index') }}" method="post" onsubmit="return consolidateOrder('selected_runs', 'route_runs_order');">
                <input type="hidden" name="action" value="add_route">
                <input type="hidden" id="route_runs_order" name="runs_order">
                <label>Name</label><input type="text" name="name" required>
                <label>End Area</label><select name="end_area"><option>East Village</option><option>Center Village</option><option>West Village</option><option>N/A</option></select>
                <label>Difficulty</label><select name="difficulty"><option>Green</option><option>Blue</option><option>Black</option></select>
                <label>Runs/Lifts</label>
                <div class="selector-container">
                    <div class="selector-box"><strong>Available</strong><ul id="available_runs">
                    {% for run in runs %}<li onclick="moveItem(this, 'selected_runs')">{{ run.name }}<span class="item-id" style="display:none;">{{run.id}}</span></li>{% endfor %}
                    </ul></div>
                    <div class="selector-box"><strong>Selected (in order)</strong><ul id="selected_runs" onclick="moveItemBack(event, 'available_runs')"></ul></div>
                </div>
                <button type="submit" class="btn btn-primary">Add Route</button>
            </form>
        </div>
        <div class="card">
            <h3>Existing Routes</h3>
            <table>
                <thead><tr><th>Name</th><th>Start Waypoint</th><th>End Area</th><th>Difficulty</th><th>Actions</th></tr></thead>
                <tbody>
                {% for route in routes %}
                    <tr>
                        <td>
                            <details><summary>{{ route.name }}</summary>
                                <ol class="details-list">
                                {% for run_name in route.run_names %}<li>{{ run_name }}</li>{% endfor %}
                                </ol>
                            </details>
                        </td>
                        <td>{{ route.start_waypoint_name }}</td>
                        <td>{{ route.end_area }}</td>
                        <td>{{ route.difficulty }}</td>
                        <td class="actions">
                            <form action="{{ url_for('index') }}" method="post" onsubmit="return confirm('Really delete {{ route.name }}?');">
                                <input type="hidden" name="action" value="delete_route">
                                <input type="hidden" name="id" value="{{ route.id }}">
                                <button type="submit" class="btn btn-danger">Delete</button>
                            </form>
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
<script>
    function moveItem(element, destId) {
        document.getElementById(destId).appendChild(element);
    }
    function moveItemBack(event, destId) {
        if (event.target.tagName === 'LI') {
            document.getElementById(destId).appendChild(event.target);
        }
    }
    function consolidateOrder(selectedListId, hiddenInputId) {
        const selectedList = document.getElementById(selectedListId);
        const ids = Array.from(selectedList.querySelectorAll('.item-id')).map(span => span.textContent);
        document.getElementById(hiddenInputId).value = ids.join(',');
        if (selectedListId === 'selected_waypoints' && ids.length < 2) {
             alert('A run or lift must have at least 2 waypoints.'); return false;
        }
        if (selectedListId === 'selected_runs' && ids.length < 1) {
             alert('A route must have at least 1 run or lift.'); return false;
        }
        return true;
    }
</script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    # Pre-fetch all data to be used in POST and GET requests
    all_waypoints = db_manager.get_all_waypoints()
    all_runs = db_manager.get_all_runs_structured()
    
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'check_route':
                start_wp_id = int(request.form['start_wp_id'])
                end_wp_id = int(request.form['end_wp_id'])
                
                if start_wp_id == end_wp_id:
                    flash("Start and End waypoints cannot be the same.", "danger")
                else:
                    # Reverse lookup map for run names from waypoint pairs
                    run_lookup = {}
                    for run in all_runs:
                        for i in range(len(run['waypoints_list']) - 1):
                            wp_pair = (run['waypoints_list'][i], run['waypoints_list'][i+1])
                            run_lookup[wp_pair] = run['name']

                    found_paths_str = []
                    for diff in ['Green', 'Blue', 'Black']:
                        path_obj = mapper.find_smart_route_to_waypoint(start_wp_id, end_wp_id, diff)
                        if path_obj and path_obj.get('waypoints'):
                            path_waypoints = path_obj['waypoints']
                            path_run_names = []
                            for i in range(len(path_waypoints) - 1):
                                wp_pair = (path_waypoints[i]['id'], path_waypoints[i+1]['id'])
                                run_name = run_lookup.get(wp_pair, 'Connector')
                                if not path_run_names or path_run_names[-1] != run_name:
                                    path_run_names.append(run_name)
                            
                            path_str = " --> ".join(path_run_names)
                            found_paths_str.append(f"<b>{diff}:</b> {path_str}")

                    if found_paths_str:
                        flash("<br>".join(found_paths_str), "success")
                    else:
                        flash("No path of any difficulty exists between these two points.", "danger")

            elif action == 'add_waypoint':
                lat = request.form.get('lat') if request.form.get('lat') else None
                lon = request.form.get('lon') if request.form.get('lon') else None
                db_manager.add_waypoint(request.form['name'], lat, lon, 0)
                flash('Waypoint added!', 'success')
            elif action == 'add_run':
                waypoints_order_str = request.form.get('waypoints_order', '')
                waypoint_ids = [int(id_str) for id_str in waypoints_order_str.split(',') if id_str]
                db_manager.add_run_lift(request.form['name'], waypoint_ids, request.form['type'], request.form['difficulty'])
                flash('Run/Lift added!', 'success')
            elif action == 'add_route':
                runs_order_str = request.form.get('runs_order', '')
                run_ids = [int(id_str) for id_str in runs_order_str.split(',') if id_str]
                db_manager.add_route(request.form['name'], run_ids, request.form['end_area'], request.form['difficulty'])
                flash('Route added!', 'success')
            elif action == 'delete_waypoint':
                db_manager.delete_waypoint(request.form['id'])
                flash('Waypoint deleted.', 'success')
            elif action == 'delete_run':
                db_manager.delete_run_lift(request.form['id'])
                flash('Run/Lift deleted.', 'success')
            elif action == 'delete_route':
                db_manager.delete_route(request.form['id'])
                flash('Route deleted.', 'success')
            elif action == 'update_waypoint':
                lat = request.form.get('lat') if request.form.get('lat') else None
                lon = request.form.get('lon') if request.form.get('lon') else None
                db_manager.update_waypoint(request.form['id'], request.form['name'], lat, lon, request.form['alt'])
                flash('Waypoint updated.', 'success')

        except sqlite3.IntegrityError:
            flash('Error: An item with that name already exists.', 'danger')
        except Exception as e:
            flash(f'An unexpected error occurred: {e}', 'danger')

        return redirect(url_for('index'))

    # --- GET REQUEST ---
    all_routes = db_manager.get_all_routes_structured()
    
    # --- Prepare data for collapsible details ---
    waypoints_by_id = {wp['id']: wp for wp in all_waypoints}
    runs_by_id = {run['id']: run for run in all_runs}

    for run in all_runs:
        run['waypoint_names'] = [waypoints_by_id.get(wp_id, {}).get('name', 'Unknown WP') for wp_id in run['waypoints_list']]
    
    for route in all_routes:
        route['run_names'] = [runs_by_id.get(run_id, {}).get('name', 'Unknown Run') for run_id in route['runs_list']]
        route['start_waypoint_name'] = "N/A"
        if route.get('runs_list'):
            first_run_id = route['runs_list'][0]
            first_run = runs_by_id.get(first_run_id)
            if first_run and first_run.get('waypoints_list'):
                first_waypoint_id = first_run['waypoints_list'][0]
                first_waypoint = waypoints_by_id.get(first_waypoint_id)
                if first_waypoint:
                    route['start_waypoint_name'] = first_waypoint['name']

    return render_template_string(HTML_TEMPLATE, waypoints=all_waypoints, runs=all_runs, routes=all_routes)

if __name__ == '__main__':
    print("Starting Web Manager...")
    print("Open your browser and go to http://<your_pi_ip_address>:1999")
    app.run(host='0.0.0.0', port=1999, debug=False)

