import requests
import threading
import time
from datetime import datetime, timedelta

# --- Configuration ---
# Coordinates for Copper Mountain, CO
COPPER_LATITUDE = 39.50
COPPER_LONGITUDE = -106.15
# How often to fetch new weather data (in seconds)
UPDATE_INTERVAL_SECONDS = 1800 # 30 minutes

# --- Shared Data and Lock ---
# This dictionary will be accessed by both the weather thread and the main app.
weather_data = {
    'current_temp': None,
    'snowfall_today': None,
    'forecast_condition': 'Loading...',
    'last_updated': None
}
data_lock = threading.Lock()

def get_latest_weather():
    """A thread-safe way for the main application to get the latest weather data."""
    with data_lock:
        return weather_data.copy()

def _fetch_weather_loop(stop_event):
    """
    The main loop for the weather thread. Fetches data periodically.
    """
    print("WEATHER_HANDLER: Thread started.")
    while not stop_event.is_set():
        try:
            # Construct the API URL for Open-Meteo
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={COPPER_LATITUDE}&longitude={COPPER_LONGITUDE}"
                "&current=temperature_2m,weather_code"
                "&daily=snowfall_sum"
                "&timezone=America%2FDenver" # Use mountain time
            )

            # Make the web request with a timeout
            response = requests.get(url, timeout=10)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            data = response.json()

            # --- Parse the JSON response ---
            current_temp = data.get('current', {}).get('temperature_2m')
            # The daily forecast is a list, today is the first item (index 0)
            snowfall_today_cm = data.get('daily', {}).get('snowfall_sum', [0])[0]
            weather_code = data.get('current', {}).get('weather_code')

            # Translate WMO weather code to a simple string
            forecast_condition = _translate_weather_code(weather_code)

            # --- Update the shared data dictionary safely ---
            with data_lock:
                weather_data['current_temp'] = f"{current_temp:.0f}C" if current_temp is not None else "N/A"
                weather_data['snowfall_today'] = f"{snowfall_today_cm:.1f} cm" if snowfall_today_cm is not None else "N/A"
                weather_data['forecast_condition'] = forecast_condition
                weather_data['last_updated'] = datetime.now().strftime("%H:%M")
            
            print(f"WEATHER_HANDLER: Successfully updated weather at {weather_data['last_updated']}.")

        except requests.exceptions.RequestException as e:
            print(f"WEATHER_HANDLER_ERROR: Could not connect to weather service: {e}")
            with data_lock:
                weather_data['forecast_condition'] = "Network Error"
        except Exception as e:
            print(f"WEATHER_HANDLER_ERROR: An unexpected error occurred: {e}")
            with data_lock:
                weather_data['forecast_condition'] = "Parse Error"

        # Wait for the specified interval before fetching again
        stop_event.wait(UPDATE_INTERVAL_SECONDS)
    
    print("WEATHER_HANDLER: Thread stopped.")


def _translate_weather_code(code):
    """Translates a WMO weather code into a simple, displayable string."""
    if code is None: return "Unknown"
    if code == 0: return "Clear"
    if code in [1, 2, 3]: return "Cloudy"
    if code in [45, 48]: return "Fog"
    if code in [51, 53, 55, 61, 63, 65, 80, 81, 82]: return "Rain"
    if code in [71, 73, 75, 77, 85, 86]: return "Snow"
    if code in [95, 96, 99]: return "T-Storm"
    return "Mixed"

def start_weather_thread():
    """
    Creates and starts the background thread for weather updates.
    Returns the thread object and the stop event.
    """
    stop_event = threading.Event()
    weather_thread = threading.Thread(
        target=_fetch_weather_loop, 
        args=(stop_event,), 
        daemon=True
    )
    weather_thread.start()
    return weather_thread, stop_event
