# ClipboardBytes (Linux)

ClipboardBytes is a lightweight, always-on-top clipboard overlay for Linux that shows exact byte size and content type in real time.

Originally created as a **visible truth signal** for clipboard operations, it has evolved into a **deterministic content classifier** for developer workflows.

---

# Core purpose

ClipboardBytes solves one problem:

    "Did my clipboard actually update — and what is it?"

It exists because clipboard operations can fail silently, lag, or paste stale content (e.g. browsers, ChatGPT, terminals, SSH, RDP).

---

# Supported content types

- Plain text with language hints
- JSON with structure size
- Python
- JavaScript
- Rust
- Go
- Java
- C#
- Bash
- HTML
- CSS
- Markdown
- Mixed multi-file clipboard payloads
- Images with resolution and byte size
- Files and URLs

---

# Core behavior

- Monitors clipboard changes in real time
- Shows UTF-8 byte size for text
- Shows detected content type
- Shows copy age
- Uses color-coded overlay borders
- Provides tooltip details (MIME type, confidence, raw formats, structure)
- Exports clipboard payloads
- Avoids guessing when classification is ambiguous

---

# Deterministic classification rule

ClipboardBytes follows a strict rule:

    Never guess. Only classify when structurally certain.

If content is ambiguous, it falls back to text and may provide hints.

Example:

    TEXT
    UTF-8
    contains python 54%, javascript 40%

---

# Mixed payload detection

ClipboardBytes detects mixed content when clipboard text contains explicit multi-file or multi-structure payloads.

Example:

    MIXED
    mixed file-bundle, json-like, js/tsx, css

This is especially useful when copying multiple files into the clipboard.

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

# UI behavior

- Displays size and content type
- Flash indicator on clipboard update
- Always-on-top overlay
- Static window size
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

Example:

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

# Export behavior

ClipboardBytes can export clipboard payloads.

Examples:

- text → .txt
- json → .json
- html → .html
- css → .css
- code → language extension
- images → .png or native format
- file lists → .txt
- mixed payloads → .txt

---

# Project structure

    ClipboardBytes/
    ├── clipboardbytes.py
    ├── clipboard_signal.py
    ├── clipboard_payload.py
    ├── clipboard_exporter.py
    ├── code_detector.py
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

- deterministic behavior
- observable state
- minimal implementation
- no daemon
- no tray icon
- no unnecessary features
- structured for future growth

---

# Status

Stable Linux-first PyQt6 implementation.

Evolving toward a compact developer clipboard HUD with deterministic inspection, export, history, and explainable classification.

---

# Author

Tor Matz Andrén
