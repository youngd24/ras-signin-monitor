# Sign-On Monitor Script

This is a clone of the code from here: https://github.com/jgknight/ras-scripts/tree/main/signon_monitor, all source credit goes to them, I just copied and hacked it.

This script monitors a Retro AIM Server instance for new user sign-ons and sends them a configurable welcome message via the management API.

It detects new users by watching for screen names that appear for the first time or who have re-signed on.

## Configuration

Configuration is handled in the `config.yaml` file:

-   `api.base_url`: The base URL of the Retro AIM Server management API (e.g., `http://localhost:8080`).
-   `monitoring.poll_interval_seconds`: How often (in seconds) the script checks for new users.
-   `monitoring.baseline_on_startup`: If `true`, the script will not message users who are already online when it starts. It will only message them after they have signed off and on again.
-   `message.sender`: The screen name that the welcome message will be sent from.
-   `message.text`: The welcome message to send to new users. You can use multi-line strings and AIM's HTML-like syntax for links.

## Usage

There are two main ways to run this script:

### 1. Using `uv` (Recommended)

If you have `uv` installed, you can run the script with a single command from the repository root. `uv` will handle creating a temporary virtual environment and installing dependencies.

```bash
uv run signon_monitor/signon_monitor.py
```

Because the script includes a dependency header, you can also run it more simply:

### 2. Using a Virtual Environment

First, create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Then, install the required packages:

```bash
pip install -r requirements.txt
```

Finally, run the script:

```bash
python signon_monitor.py
```
