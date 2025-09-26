import time
import queue
import gps # Use the system-level 'gps' library that is proven to work
import math

# --- Conversion Constants ---
MPS_TO_KPH = 3.6
EARTH_RADIUS_METERS = 6371000

def haversine_distance(p1, p2):
    """Calculates the distance between two lat/lon points."""
    lat1_rad, lon1_rad = math.radians(p1['lat']), math.radians(p1['lon'])
    lat2_rad, lon2_rad = math.radians(p2['lat']), math.radians(p2['lon'])
    dlon, dlat = lon2_rad - lon1_rad, lat2_rad - lat1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_METERS * c

def calculate_heading(p1, p2):
    """Calculates the bearing from point 1 to point 2."""
    lat1_rad, lon1_rad = math.radians(p1['lat']), math.radians(p1['lon'])
    lat2_rad, lon2_rad = math.radians(p2['lat']), math.radians(p2['lon'])
    dLon = lon2_rad - lon1_rad
    y = math.sin(dLon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dLon)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360

def gps_poller(gps_queue):
    """
    Continuously polls gpsd, calculates heading and incline, and puts the
    full data packet into the gps_queue.
    """
    session = None
    last_valid_report = None

    while True: # Keep trying to connect
        try:
            session = gps.gps(mode=gps.WATCH_ENABLE)
            print("GPS_HANDLER: Thread started, successfully connected to gpsd.")
            
            while True:
                report = session.next()
                if report['class'] == 'TPV':
                    new_data = {
                        'fix': False, 'speed_kph': 0, 'speed_mps': 0,
                        'heading': 0, 'incline_deg': 0
                    }
                    
                    if getattr(report, 'mode', 1) >= 2:
                        # We have at least a 2D fix
                        new_data.update({
                            'fix': True,
                            'lat': getattr(report, 'lat', None),
                            'lon': getattr(report, 'lon', None),
                            'alt_m': getattr(report, 'alt', 0.0),
                            'speed_mps': getattr(report, 'speed', 0.0),
                            'speed_kph': getattr(report, 'speed', 0.0) * MPS_TO_KPH
                        })

                        # Calculations requiring two points
                        if last_valid_report:
                            distance = haversine_distance(last_valid_report, new_data)
                            alt_change = new_data['alt_m'] - last_valid_report['alt_m']
                            
                            if distance > 1.0: # Only calculate if we've moved a meter
                                new_data['heading'] = calculate_heading(last_valid_report, new_data)
                                # Clamp incline to prevent extreme values from GPS errors
                                incline_rad = math.atan2(alt_change, distance)
                                new_data['incline_deg'] = max(-45, min(45, math.degrees(incline_rad)))
                        
                        last_valid_report = new_data.copy()

                    gps_queue.put(new_data)
                
                time.sleep(0.1)

        except Exception as e:
            print(f"GPS_HANDLER: Connection lost or failed: {e}. Retrying in 5 seconds...")
            if session:
                session.close()
            last_valid_report = None
            gps_queue.put({'fix': False}) # Ensure UI updates to 'no fix'
            time.sleep(5)
        finally:
            if session:
                session.close()
                
    print("GPS_HANDLER: Thread stopped.")

