#!/usr/bin/env python3
# /// script
# dependencies = [
#     "requests",
#     "pyyaml",
#     "setproctitle",
# ]
# ///

import os
import sys
import time
from datetime import datetime, timedelta
import requests
import yaml

try:
    from setproctitle import setproctitle
    setproctitle("signon-monitor")
except ImportError:
    # setproctitle not available, continue without it
    pass

# Force unbuffered output for real-time logging
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

def load_config():
    """Loads the configuration from config.yaml."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def log(message):
    """Prints a message with a timestamp and flushes immediately."""
    log_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(log_message, flush=True)

user_session_info = {}  # screen_name -> online_seconds
user_last_messaged = {}  # screen_name -> datetime when last messaged

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

def should_message_user(screen_name, cooldown_minutes):
    """Check if enough time has passed since last messaging this user."""
    if screen_name not in user_last_messaged:
        return True
    
    time_since_last_message = datetime.now() - user_last_messaged[screen_name]
    cooldown_period = timedelta(minutes=cooldown_minutes)
    
    if time_since_last_message < cooldown_period:
        remaining_time = cooldown_period - time_since_last_message
        remaining_minutes = int(remaining_time.total_seconds() / 60)
        remaining_seconds = int(remaining_time.total_seconds() % 60)
        log(f"Skipping {screen_name} - cooldown active ({remaining_minutes}m {remaining_seconds}s remaining)")
        return False
    
    return True

def send_instant_message(config, user):
    """Sends an instant message to a user."""
    screen_name = user.get("screen_name")
    
    if user.get("is_icq", False):
        log(f"Not sending msg to ICQ user {screen_name}")
        return
    
    # Check if user is in the ignored list
    ignored_users = config.get("message", {}).get("ignored_users", [])
    if screen_name in ignored_users:
        log(f"Skipping ignored user: {screen_name}")
        return
    
    # Get cooldown period from config
    cooldown_minutes = config.get("message", {}).get("cooldown_minutes", 10)
    if not should_message_user(screen_name, cooldown_minutes):
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
        # Record the time we messaged this user
        user_last_messaged[screen_name] = datetime.now()
    except requests.exceptions.RequestException as e:
        log(f"Error sending message to {screen_name}: {e}")

def cleanup_offline_users(online_screen_names, cooldown_minutes):
    """Remove offline users from tracking dictionaries based on configurable cooldown."""
    # Prune users who are no longer online from session info
    for seen_user in list(user_session_info.keys()):
        if seen_user not in online_screen_names:
            log(f"User {seen_user} has signed off. Removing from seen list.")
            del user_session_info[seen_user]
    
    # Prune users who are no longer online from message tracking
    # Keep message history for offline users in case they come back within cooldown period
    for messaged_user in list(user_last_messaged.keys()):
        if messaged_user not in online_screen_names:
            # Only remove from message tracking if it's been more than cooldown period
            # This prevents immediate re-messaging if they reconnect quickly
            time_since_last_message = datetime.now() - user_last_messaged[messaged_user]
            if time_since_last_message > timedelta(minutes=cooldown_minutes):
                log(f"Removing {messaged_user} from message cooldown tracking (offline > {cooldown_minutes} min)")
                del user_last_messaged[messaged_user]

def run_monitor():
    """Runs the monitoring loop."""
    config = load_config()
    
    # Log startup configuration
    log(f"Monitoring server at {config['api']['base_url']}")
    
    # Log ignored users configuration
    ignored_users = config.get("message", {}).get("ignored_users", [])
    if ignored_users:
        log(f"Configured to ignore users: {', '.join(ignored_users)}")
    else:
        log("No users configured to be ignored")
    
    # Log cooldown configuration
    cooldown_minutes = config.get("message", {}).get("cooldown_minutes", 10)
    log(f"Message cooldown period: {cooldown_minutes} minutes")
    
    if config.get("monitoring", {}).get("baseline_on_startup", True):
        log("Establishing baseline of currently online users...")
        initial_users_response = get_online_users(config)
        initial_sessions = initial_users_response.get("sessions", [])
        
        for user in initial_sessions:
            screen_name = user.get("screen_name")
            online_seconds = user.get("online_seconds")
            if screen_name and online_seconds is not None:
                user_session_info[screen_name] = online_seconds
        
        log(f"Baseline established with {len(user_session_info)} users. Monitoring for new sign-ons.")
    
    while True:
        online_users_response = get_online_users(config)
        sessions = online_users_response.get("sessions", [])
        online_screen_names = [user.get("screen_name") for user in sessions]
        
        # Clean up offline users
        cooldown_minutes = config.get("message", {}).get("cooldown_minutes", 10)
        cleanup_offline_users(online_screen_names, cooldown_minutes)
        
        for user in sessions:
            screen_name = user.get("screen_name")
            online_seconds = user.get("online_seconds")
            
            if not screen_name or online_seconds is None:
                continue
            
            # Get ignored users list from config
            ignored_users = config.get("message", {}).get("ignored_users", [])
            
            if screen_name not in user_session_info:
                log(f"New user detected: {screen_name}")
                if screen_name in ignored_users:
                    log(f"Skipping ignored user: {screen_name}")
                else:
                    time.sleep(10)
                    send_instant_message(config, user)
                user_session_info[screen_name] = online_seconds
            
            elif online_seconds < user_session_info[screen_name]:
                log(f"User {screen_name} has re-signed on.")
                if screen_name in ignored_users:
                    log(f"Skipping ignored user: {screen_name}")
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
