import subprocess
import threading
import os

# Define the path for the temporary WAV file. Using /tmp ensures it's cleaned up on reboot.
TEMP_WAV_FILE = "/tmp/smartgoggles_tts.wav"

def speak(text_to_speak):
    """
    Generates and plays audio from a string of text in a non-blocking way.
    It uses the system's pico2wave (for TTS) and aplay (for playback) commands.

    Args:
        text_to_speak (str): The sentence to be spoken.
    """
    # This check prevents errors if the function is called with no text.
    if not text_to_speak:
        return

    # To avoid freezing the main application while the audio is generated and played,
    # we run the commands in a separate background thread.
    playback_thread = threading.Thread(target=_generate_and_play, args=(text_to_speak,), daemon=True)
    playback_thread.start()

def _generate_and_play(text):
    """
    Private helper function that runs in a thread to handle the audio process.
    """
    try:
        # Step 1: Generate the WAV file from text using pico2wave.
        # The '-w' flag specifies the output file.
        subprocess.run(['pico2wave', '-w', TEMP_WAV_FILE, text], check=True)

        # Step 2: Play the generated WAV file using aplay.
        # The '-q' flag makes the playback quiet (suppresses status messages).
        subprocess.run(['aplay', '-q', TEMP_WAV_FILE], check=True)

    except FileNotFoundError:
        # This error occurs if pico2wave or aplay are not installed.
        print("AUDIO_HANDLER_ERROR: 'pico2wave' or 'aplay' not found. Please install with 'sudo apt-get install libttspico-utils alsa-utils'")
    except subprocess.CalledProcessError as e:
        # This catches any errors from the commands themselves.
        print(f"AUDIO_HANDLER_ERROR: An error occurred during audio processing: {e}")
    except Exception as e:
        print(f"AUDIO_HANDLER_ERROR: An unexpected error occurred: {e}")
    finally:
        # Step 3: Clean up by deleting the temporary WAV file.
        if os.path.exists(TEMP_WAV_FILE):
            os.remove(TEMP_WAV_FILE)
