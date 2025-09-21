import cv2
import os
import threading
import queue
from datetime import datetime
import time

class VideoRecorder:
    """
    Handles video recording with an enhanced GPS and status overlay.
    It now reads both live GPS data and application state (like current run name).
    """
    def __init__(self, gps_queue, recorder_data, data_lock):
        self.gps_queue = gps_queue
        self.recorder_data = recorder_data # Shared dict for app state
        self.data_lock = data_lock         # Lock for the recorder_data dict
        self._stop_event = threading.Event()
        self.recording_thread = None
        
        # Ensure the recordings directory exists
        self.output_dir = "recordings"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def is_recording(self):
        return self.recording_thread is not None and self.recording_thread.is_alive()

    def start(self):
        if not self.is_recording():
            self._stop_event.clear()
            self.recording_thread = threading.Thread(target=self._record_loop, daemon=True)
            self.recording_thread.start()
            print("RECORDER: Recording started.")

    def stop(self):
        if self.is_recording():
            self._stop_event.set()
            # Wait for the thread to finish writing the file
            self.recording_thread.join(timeout=5.0) # Add a timeout
            self.recording_thread = None
            print("RECORDER: Recording stopped and file saved.")

    def _record_loop(self):
        """The main recording loop that runs in its own thread."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("RECORDER ERROR: Cannot open webcam.")
            return

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 24 

        filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".mp4"
        filepath = os.path.join(self.output_dir, filename)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(filepath, fourcc, fps, (width, height))

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_color = (255, 255, 255) # White
        
        latest_gps_data = {}
        latest_app_data = {}

        while not self._stop_event.is_set():
            ret, frame = cap.read()
            if not ret: break

            # Check for new GPS data from the queue
            try:
                latest_gps_data = self.gps_queue.get_nowait()
            except queue.Empty:
                pass 

            # Check for new application state from the shared dictionary
            with self.data_lock:
                latest_app_data = self.recorder_data.copy()

            # --- Prepare all overlay text ---
            speed_kph = latest_gps_data.get('speed_kph', 0.0)
            alt_m = latest_gps_data.get('alt_m', 0.0)
            gps_fix = latest_gps_data.get('fix', False)
            current_run = latest_app_data.get('current_run_name', 'N/A')
            
            speed_text = f"Speed: {speed_kph:.1f} kph"
            alt_text = f"Altitude: {alt_m:.0f} m"
            fix_text = "GPS: OK" if gps_fix else "GPS: NO FIX"
            run_text = f"On: {current_run}"

            # --- Draw the overlay ---
            # Add a semi-transparent black background for readability
            overlay_bg = frame.copy()
            cv2.rectangle(overlay_bg, (10, 10), (300, 140), (0,0,0), -1)
            alpha = 0.6
            frame = cv2.addWeighted(overlay_bg, alpha, frame, 1 - alpha, 0)
            
            # Draw the text on the frame
            cv2.putText(frame, speed_text, (20, 40), font, 0.8, font_color, 2)
            cv2.putText(frame, alt_text, (20, 70), font, 0.8, font_color, 2)
            cv2.putText(frame, run_text, (20, 100), font, 0.8, font_color, 2)
            cv2.putText(frame, fix_text, (width - 150, 30), font, 0.7, font_color, 2)
            cv2.putText(frame, datetime.now().strftime("%H:%M:%S"), (width - 150, 60), font, 0.7, font_color, 2)

            writer.write(frame)

        # --- Cleanup ---
        cap.release()
        writer.release()
        cv2.destroyAllWindows()

