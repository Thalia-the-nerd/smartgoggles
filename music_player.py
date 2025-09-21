import os
import subprocess
import threading
import time

# --- Configuration ---
# The base directory where your music is stored. Assumes a 'music' folder in your home directory.
MUSIC_BASE_DIR = os.path.expanduser("~/music")

class MusicPlayer:
    """
    Manages music playback from a specified directory in a non-blocking way.
    """
    def __init__(self):
        self.playlists = {}
        self.current_playlist_name = None
        self.current_track_index = 0
        self.playback_process = None
        self.is_playing = False
        self._scan_for_playlists()

    def _scan_for_playlists(self):
        """Scans the music directory for subdirectories, treating each as a playlist."""
        print("MUSIC_PLAYER: Scanning for playlists...")
        if not os.path.isdir(MUSIC_BASE_DIR):
            print(f"MUSIC_PLAYER_WARNING: Music directory not found at {MUSIC_BASE_DIR}")
            return

        for playlist_name in os.listdir(MUSIC_BASE_DIR):
            playlist_path = os.path.join(MUSIC_BASE_DIR, playlist_name)
            if os.path.isdir(playlist_path):
                tracks = sorted([
                    os.path.join(playlist_path, f) 
                    for f in os.listdir(playlist_path) 
                    if f.lower().endswith(('.mp3', '.wav'))
                ])
                if tracks:
                    self.playlists[playlist_name] = tracks
                    print(f"MUSIC_PLAYER: Found playlist '{playlist_name}' with {len(tracks)} tracks.")
        
        # Set the first found playlist as the default
        if self.playlists:
            self.current_playlist_name = list(self.playlists.keys())[0]

    def get_current_track_info(self):
        """Returns the name of the currently selected track."""
        if not self.current_playlist_name or not self.playlists.get(self.current_playlist_name):
            return "No Music Found"
        
        track_path = self.playlists[self.current_playlist_name][self.current_track_index]
        # Return just the filename without the path or extension
        return os.path.splitext(os.path.basename(track_path))[0]

    def _play_current_track(self):
        """Stops any current playback and starts the selected track."""
        if self.playback_process:
            self.playback_process.terminate()
            self.playback_process.wait()

        if not self.current_playlist_name:
            return

        track_path = self.playlists[self.current_playlist_name][self.current_track_index]
        
        # Using subprocess.Popen allows the music to play in the background.
        self.playback_process = subprocess.Popen(
            ['mpg123', '-q', track_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.is_playing = True

    def toggle_playback(self):
        """Plays or pauses the current track."""
        if not self.current_playlist_name:
            return

        if self.is_playing:
            # Pausing by stopping the process. Resuming will start from the beginning.
            # True pause/resume is more complex and requires more advanced libraries.
            if self.playback_process:
                self.playback_process.terminate()
                self.playback_process = None
            self.is_playing = False
        else:
            self._play_current_track()

    def next_track(self):
        """Skips to the next track in the playlist."""
        if not self.current_playlist_name:
            return
            
        playlist = self.playlists[self.current_playlist_name]
        self.current_track_index = (self.current_track_index + 1) % len(playlist)
        if self.is_playing:
            self._play_current_track()

    def previous_track(self):
        """Skips to the previous track in the playlist."""
        if not self.current_playlist_name:
            return

        playlist = self.playlists[self.current_playlist_name]
        self.current_track_index = (self.current_track_index - 1 + len(playlist)) % len(playlist)
        if self.is_playing:
            self._play_current_track()
