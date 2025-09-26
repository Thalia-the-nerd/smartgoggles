import os
import sqlite3
from flask import Flask, render_template_string, request, abort
from datetime import datetime

# --- Configuration ---
LOG_DIRECTORY = 'daily_logs'

app = Flask(__name__)

# --- Helper Functions ---
def get_available_logs():
    """Scans the log directory for valid .db files and returns a sorted list of dates."""
    if not os.path.exists(LOG_DIRECTORY):
        return []
    
    log_files = []
    for filename in os.listdir(LOG_DIRECTORY):
        if filename.endswith('.db'):
            try:
                # Expecting format like YYYY-MM-DD.db
                date_part = filename.split('.')[0]
                log_date = datetime.strptime(date_part, '%Y-%m-%d')
                log_files.append({'filename': filename, 'date': log_date})
            except ValueError:
                continue # Ignore files that don't match the date format
                
    # Sort by date, newest first
    return sorted(log_files, key=lambda x: x['date'], reverse=True)

def get_log_data(db_filename):
    """Fetches all trip log entries from a specific daily database file."""
    db_path = os.path.join(LOG_DIRECTORY, db_filename)
    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trip_log'")
        if cursor.fetchone() is None:
            return [] # Return empty list if table doesn't exist

        cursor.execute("SELECT timestamp, lat, lon, alt, speed FROM trip_log ORDER BY timestamp ASC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"Database error reading {db_filename}: {e}")
        return None
    finally:
        if conn:
            conn.close()

# --- HTML Template ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartGoggles Daily Logs</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f4f4f9; color: #333; margin: 0; padding: 1rem; }
        .container { max-width: 1200px; margin: auto; background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1, h2 { color: #0056b3; border-bottom: 2px solid #e9ecef; padding-bottom: 0.5rem; }
        .log-selector { margin-bottom: 2rem; }
        .log-selector a { text-decoration: none; color: #007bff; background: #e9ecef; padding: 0.5rem 1rem; border-radius: 4px; margin-right: 0.5rem; margin-bottom: 0.5rem; display: inline-block; }
        .log-selector a.active { background: #007bff; color: #fff; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #dee2e6; }
        th { background-color: #f8f9fa; }
        tr:nth-child(even) { background-color: #f8f9fa; }
        .no-data { text-align: center; color: #6c757d; padding: 2rem; }
    </style>
</head>
<body>
<div class="container">
    <h1>SmartGoggles Daily Log Viewer</h1>
    <div class="log-selector">
        <h2>Available Logs</h2>
        {% if logs %}
            {% for log in logs %}
                <a href="{{ url_for('view_log', filename=log.filename) }}" class="{{ 'active' if log.filename == active_log else '' }}">
                    {{ log.date.strftime('%A, %b %d, %Y') }}
                </a>
            {% endfor %}
        {% else %}
            <p class="no-data">No daily logs found in the '{{ log_dir }}' directory.</p>
        {% endif %}
    </div>

    {% if selected_log_data is not none %}
        <h2>Log Entries for {{ active_log_date }}</h2>
        {% if selected_log_data %}
            <table>
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Latitude</th>
                        <th>Longitude</th>
                        <th>Altitude (m)</th>
                        <th>Speed (m/s)</th>
                    </tr>
                </thead>
                <tbody>
                {% for entry in selected_log_data %}
                    <tr>
                        <td>{{ entry.timestamp.split('.')[0] }}</td>
                        <td>{{ "%.5f"|format(entry.lat) }}</td>
                        <td>{{ "%.5f"|format(entry.lon) }}</td>
                        <td>{{ "%.1f"|format(entry.alt) }}</td>
                        <td>{{ "%.2f"|format(entry.speed) }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p class="no-data">No trip data was recorded on this day.</p>
        {% endif %}
    {% endif %}
</div>
</body>
</html>
"""

# --- Flask Routes ---
@app.route('/')
def index():
    """Displays the list of available logs, with the most recent one selected by default."""
    logs = get_available_logs()
    if not logs:
        return render_template_string(HTML_TEMPLATE, logs=logs, log_dir=LOG_DIRECTORY)
    
    # Redirect to the most recent log
    from flask import redirect, url_for
    return redirect(url_for('view_log', filename=logs[0]['filename']))

@app.route('/log/<filename>')
def view_log(filename):
    """Displays the data for a specific log file."""
    if '..' in filename or not filename.endswith('.db'):
        abort(400) # Bad request

    logs = get_available_logs()
    log_data = get_log_data(filename)
    
    if log_data is None:
        abort(404) # Not found

    active_log_date = ""
    try:
        active_log_date = datetime.strptime(filename.split('.')[0], '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        pass

    return render_template_string(
        HTML_TEMPLATE, 
        logs=logs, 
        selected_log_data=log_data,
        active_log=filename,
        active_log_date=active_log_date,
        log_dir=LOG_DIRECTORY
    )

if __name__ == '__main__':
    print("Starting Daily Log Viewer...")
    print(f"Ensure your daily logs are in the '{LOG_DIRECTORY}' directory.")
    print("Open your browser and go to http://<your_pi_ip_address>:2000")
    app.run(host='0.0.0.0', port=2000, debug=False)

