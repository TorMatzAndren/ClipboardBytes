# ClipboardBytes (Linux)

ClipboardBytes is a tiny desktop overlay that shows the current clipboard text size in bytes.

It exists as a **visible truth signal** for copy/paste workflows where clipboard operations can fail silently, lag, or paste stale content (e.g. browsers, ChatGPT, terminals, SSH, RDP).

---

# Requirements

## System

- Debian Linux (X11 recommended)
- Python 3

## Dependencies

Install required packages:

    sudo apt update
    sudo apt install python3 python3-pyqt6

No virtual environment is required.

---

# Install

Create a project directory:

    mkdir -p ~/projects/ClipboardBytes
    cd ~/projects/ClipboardBytes

Place all project files in this directory.

---

# Run

Run directly:

    python3 clipboardbytes.py

---

# Launcher (recommended)

Create a launcher script:

    cat > ~/projects/ClipboardBytes/run_clipboardbytes.sh <<'SCRIPT'
    #!/usr/bin/env bash
    cd "$HOME/projects/ClipboardBytes" || exit 1
    exec /usr/bin/python3 clipboardbytes.py
    SCRIPT

    chmod +x ~/projects/ClipboardBytes/run_clipboardbytes.sh

Run with:

    ~/projects/ClipboardBytes/run_clipboardbytes.sh

---

# Run without terminal

    nohup ~/projects/ClipboardBytes/run_clipboardbytes.sh >/dev/null 2>&1 &

---

# Autostart

    mkdir -p ~/.config/autostart

    cat > ~/.config/autostart/clipboardbytes.desktop <<EOF
    [Desktop Entry]
    Type=Application
    Name=ClipboardBytes
    Comment=Clipboard byte counter overlay
    Exec=$HOME/projects/ClipboardBytes/run_clipboardbytes.sh
    Terminal=false
    X-GNOME-Autostart-enabled=true
    EOF

---

# Behavior

- Shows: <N> bytes
- Counts clipboard text as UTF-8 bytes
- Flashes green for about 2 seconds on new clipboard data
- White text normally
- Always-on-top overlay
- One window on startup

Right-click menu:

- Lock / Unlock
- Add clone
- Remove
- Exit

---

# Persistence

State is stored in:

    ~/.config/clipboardbytes/state.json

Only locked windows are saved.

Example structure:

    {
      "version": 1,
      "windows": [
        {
          "id": "stable-window-id",
          "screen": "HDMI-1",
          "x": 220,
          "y": 1032,
          "locked": true
        }
      ]
    }

---

# Project structure

    ClipboardBytes/
    ├── clipboardbytes.py
    ├── clipboard_signal.py
    ├── overlay_window.py
    ├── window_manager.py
    ├── config_store.py
    ├── run_clipboardbytes.sh
    └── README.md

---

# Platform notes

## X11

Primary target. Expected to work correctly.

## Wayland

Limitations may include:

- always-on-top not guaranteed
- window positioning restrictions
- overlay behavior differences

## Taskbars / panels

ClipboardBytes does NOT override taskbars or panels.

This is intentional for cross-desktop compatibility.

---

# Stop ClipboardBytes

From menu:

- Right-click → Exit

Or from terminal:

    pkill -f clipboardbytes.py

---

# Design principles

- minimal implementation
- deterministic behavior
- observable state
- no daemon
- no tray icon
- no unnecessary features
- structured for future growth

---

# Summary

ClipboardBytes solves one problem:

    "Did my clipboard actually update — and how big is it?"

