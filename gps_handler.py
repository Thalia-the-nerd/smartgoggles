import time
import queue
import gps # Use the system-level 'gps' library that is proven to work

# --- Conversion Constants ---
MPS_TO_KPH = 3.6

def gps_poller(gps_queue):
    """
    Continuously polls the gpsd daemon using the system's 'gps' library
    and puts new data into the gps_queue.
    """
    session = None
    while True: # Keep trying to connect
        try:
            # Connect to the local gpsd daemon
            session = gps.gps(mode=gps.WATCH_ENABLE)
            print("GPS_HANDLER: Thread started, successfully connected to gpsd.")
            
            while True:
                report = session.next()
                # We need TPV reports for our data
                if report['class'] == 'TPV':
                    new_data = {}
                    # mode 3 = 3D fix, mode 2 = 2D fix
                    if getattr(report, 'mode', 1) >= 2:
                        new_data['fix'] = True
                        new_data['lat'] = getattr(report, 'lat', None)
                        new_data['lon'] = getattr(report, 'lon', None)
                        speed_mps = getattr(report, 'speed', 0.0)
                        new_data['speed_mps'] = speed_mps
                        new_data['speed_kph'] = speed_mps * MPS_TO_KPH
                        new_data['alt_m'] = getattr(report, 'alt', 0.0) # alt is altMSL
                    else:
                        new_data['fix'] = False
                        new_data['speed_kph'] = 0
                        new_data['speed_mps'] = 0
                    
                    # Put the new data dictionary into the queue for the main app
                    gps_queue.put(new_data)
                
                time.sleep(0.1)

        except Exception as e:
            print(f"GPS_HANDLER: Connection lost or failed: {e}. Retrying in 5 seconds...")
            if session:
                session.close()
            # Put a "no fix" message to ensure the UI updates
            gps_queue.put({'fix': False})
            time.sleep(5)
        finally:
            if session:
                session.close()
                
    print("GPS_HANDLER: Thread stopped.")

