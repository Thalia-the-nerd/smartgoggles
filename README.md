Smart Goggles: An Open-Source Skiing HUD

<p align="center">
<img src="https://www.google.com/search?q=https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python Version">
<img src="https://www.google.com/search?q=https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPLv3">
<img src="https://www.google.com/search?q=https://img.shields.io/badge/platform-Raspberry%2520Pi-lightgrey.svg" alt="Platform: Raspberry Pi">
<img src="https://www.google.com/search?q=https://img.shields.io/badge/status-in--development-orange.svg" alt="Status: In Development">
</p>

<p align="center">
A custom, Raspberry Pi-powered heads-up display that fits inside your ski goggles. Designed for the skiing and engineering enthusiast, this project provides a rich, offline-first experience with real-time stats, full resort navigation, and performance tracking.
</p>

<p align="center">
[Animation of the Smart Goggles UI in action]
</p>
📖 Table of Contents

    Key Features

    System Requirements

    Installation Guide

    Usage

    Project Structure

    Contributing

    License

🚀 Key Features

The Smart Goggles are packed with features designed to enhance your on-mountain experience, all working completely offline.

Feature
	

Description

Live HUD
	

The main screen displays your current speed, altitude, the time, and a real-time inclinometer showing the steepness of the current slope.

Full Resort Navigation
	

Get turn-by-turn directions between any two points on the mountain. Filter routes by difficulty and even reverse your route to get back to the start.

Performance Analytics
	

Automatically logs every run. Displays a post-run summary with your time, top speed, and vertical drop. End-of-day screens show a "Performance Profile" and "Day's Best" achievements.

Daily Logging & Web Viewer
	

All GPS tracks and run data are automatically saved to a new database file each day. A separate, simple web app allows you to review your daily stats.

Safety & Utility
	

Includes dedicated screens for the Ski Patrol's contact number, a "Last Lift Warning" with a live countdown, a digital compass, and a diagnostic screen.

Offline First
	

No cell service or Wi-Fi is required on the mountain. All mapping, navigation, and logging are handled directly on the device.
🛠️ System Requirements
Hardware

    Core: Raspberry Pi (Zero 2 W recommended for size and performance)

    Display: Waveshare 1.51" OLED Display (or compatible)

    GPS: A GPS module compatible with gpsd (e.g., Adafruit Ultimate GPS)

    Input: A Bluetooth numeric keypad

    Power: A portable USB power bank

    (Optional): A Raspberry Pi Camera Module for the video recording feature.

Software

    OS: Raspberry Pi OS (Legacy, 32-bit)

    Dependencies: gpsd, pico2wave, opencv, and Python 3.9+.

⚙️ Installation Guide
1. System Dependencies

First, ensure your Raspberry Pi is up-to-date and install the required system libraries:

sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install gpsd gpsd-clients python3-gps
sudo apt-get install libttspico-utils alsa-utils
sudo apt-get install python3-opencv

2. Clone & Install

Next, clone the repository and install the necessary Python packages:

git clone <your-repository-url>
cd smart-goggles
pip install -r requirements.txt

(Note: A requirements.txt file listing libraries like evdev, Pillow, Flask is required)
3. Configuration

    Edit variables.py: Set your local Ski Patrol's phone number and the last lift time.

    Edit main_app.py: Ensure the KEYPAD_DEVICE_PATH variable matches the device path on your system.

4. Set Up the Database

    Populate the waypoints.csv, runs_lifts.csv, and routes.csv files with your home resort's data.

    Run the import script to build the main database:

    python importdb.py

💡 Usage

The project is split into three separate applications that can be run from the command line.

    Main Goggles App: To start the HUD, run the boot script. sudo is often required for direct hardware access.

    sudo python boot.py

    Database Web Manager: To add or edit your resort's map data, run the main web app:

    python web_manager.py

    Daily Log Viewer: To review your daily skiing history from a browser, run the log viewer:

    python daily_log_viewer.py

📁 Project Structure

A brief overview of the key files in this project:

├── boot.py               # Main entry point, initializes hardware and threads
├── main_app.py           # Core application logic, UI state, and input handling
├── ui_manager.py         # Handles all drawing operations to the OLED screen
├── db_manager.py         # Manages all interactions with the SQLite databases
├── mapper.py             # Contains pathfinding and navigation logic
├── trip_logger.py        # Background thread for logging GPS data to daily DBs
├── web_manager.py        # Flask app for managing the main resort database
├── daily_log_viewer.py   # Flask app for viewing daily log files
└── variables.py          # User-configurable settings (phone numbers, times)

🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.
📜 License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for more details.
