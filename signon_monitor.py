#!/usr/bin/env python3
# /// script
# dependencies = [
#   "requests",
#   "pyyaml",
# ]
# ///

import os
import sys
import time
from datetime import datetime

import requests
import yaml


def load_config():
    """Loads the configuration from config.yaml."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def log(message):
    """Prints a message with a timestamp."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


user_session_info = {}  # screen_name -> online_seconds


def get_online_users(config):
    """Gets the list of online users from the API."""
    url = f"{config['api']['base_url']}/session"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log(f"Error fetching online users: {e}")
        return {}


def send_instant_message(config, user):
    """Sends an instant message to a user."""
    screen_name = user.get("screen_name")

    if user.get("is_icq", False):
        log(f"Not sending msg to ICQ user {screen_name}")
        return

    url = f"{config['api']['base_url']}/instant-message"
    data = {
        "to": screen_name,
        "from": config["message"]["sender"],
        "text": config["message"]["text"],
    }
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        log(f"Successfully sent message to {screen_name}")
    except requests.exceptions.RequestException as e:
        log(f"Error sending message to {screen_name}: {e}")


def run_monitor():
    """Runs the monitoring loop."""
    config = load_config()

    log(f"Monitoring server at {config['api']['base_url']}")

    if config.get("monitoring", {}).get("baseline_on_startup", True):
        log("Establishing baseline of currently online users...")
        initial_users_response = get_online_users(config)
        initial_sessions = initial_users_response.get("sessions", [])
        for user in initial_sessions:
            screen_name = user.get("screen_name")
            online_seconds = user.get("online_seconds")
            if screen_name and online_seconds is not None:
                user_session_info[screen_name] = online_seconds
        log(
            f"Baseline established with {len(user_session_info)} users. Monitoring for new sign-ons."
        )

    while True:
        online_users_response = get_online_users(config)
        sessions = online_users_response.get("sessions", [])

        online_screen_names = [user.get("screen_name") for user in sessions]

        # Prune users who are no longer online
        for seen_user in list(user_session_info.keys()):
            if seen_user not in online_screen_names:
                log(f"User {seen_user} has signed off. Removing from seen list.")
                del user_session_info[seen_user]

        for user in sessions:
            screen_name = user.get("screen_name")
            online_seconds = user.get("online_seconds")

            if not screen_name or online_seconds is None:
                continue

            if screen_name not in user_session_info:
                log(f"New user detected: {screen_name}")
                if screen_name == "Milton":
                    log(f"Skipping bot {screen_name}")
                else:
                    time.sleep(10)
                    send_instant_message(config, user)
                    user_session_info[screen_name] = online_seconds

            elif online_seconds < user_session_info[screen_name]:
                log(f"User {screen_name} has re-signed on.")
                if screen_name == "Milton":
                    log(f"Skipping bot... {screen_name}")
                else:
                    time.sleep(10)
                    send_instant_message(config, user)
                    user_session_info[screen_name] = online_seconds
            else:
                # Update the online time for the user
                user_session_info[screen_name] = online_seconds

        time.sleep(config["monitoring"]["poll_interval_seconds"])


if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        log("Ctrl-C detected. Goodbye!")
        sys.exit(0)
