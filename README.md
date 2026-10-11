# ClipboardBytes (Linux)

ClipboardBytes is a lightweight Linux clipboard inspector and developer clipboard HUD that shows exact byte size and content type in real time.

Originally created as a **visible truth signal** for clipboard operations, it has evolved into a **deterministic content classifier** for developer workflows, including first-class Codex handoff transcripts and Jarri clipboard provenance.

---

# Core purpose

ClipboardBytes solves one problem:

    "Did my clipboard actually update — and what is it?"

It exists because clipboard operations can fail silently, lag, or paste stale content (e.g. browsers, ChatGPT, terminals, SSH, RDP).

---

# Supported content types

- Plain text with language hints
- Codex handoff transcripts
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

## Optional clipboard event diagnostics

For X11 duplicate-event investigations, start ClipboardBytes with
`CLIPBOARDBYTES_DIAGNOSTICS=1`. Diagnostics are disabled by default and are
written as JSON Lines to stderr. For example:

```bash
CLIPBOARDBYTES_DIAGNOSTICS=1 ./run_clipboardbytes.sh --headless \
  2> /tmp/clipboardbytes-diagnostics.jsonl
```

Stop the already-running ClipboardBytes instance before starting this command
so the diagnostic run does not create a second observer. The trace records
callback sequence and timing, process/thread identity, advertised MIME types,
payload kind and SHA-256, acquisition result and duration, X11 CLIPBOARD and
CLIPBOARD_MANAGER window/PID identities and owner executable when available,
and correlated enqueue/register completion events. It never records clipboard
payload bytes. The hash can still identify
repeated content, so treat the diagnostic file as sensitive and remove it when
the investigation is complete.

### XFCE clipboard persistence provenance

On X11, ClipboardBytes treats a byte-identical follow-up as the same logical
copy only when the previous callback came from a non-manager owner and the
current owner is confirmed as the live `xfsettingsd` process that also owns
`CLIPBOARD_MANAGER`. The two selections may belong to distinct windows in that
same X client. ClipboardBytes resolves their process identity through the
X-Resource extension when available, with `_NET_WM_PID` as fallback;
unavailable or mismatched identity fails open. Clipboard ownership must be
stable across the current capture. Payload bytes, kind, and MIME type must match exactly.
Only that persistence takeover callback is omitted from provenance; its
original application observation is retained. Recopying the same content from
an application creates another observation, and ownership changes to other
applications are retained even when bytes match. If X11 ownership, manager
selection, process identity, or payload data is unavailable or inconsistent,
ClipboardBytes keeps the observation. No time window or hash-only rule is
used.

---

# Deterministic classification rule

ClipboardBytes follows a strict rule:

    Never guess. Only classify when structurally certain.

If content is ambiguous, it falls back to text and may provide hints.

Explicit artifact identity takes precedence over embedded syntax inference.
For example, a canonical Codex handoff remains `CODEX` even when the
transcript contains Python, Rust, shell commands, diffs, JSON, or prose.

Example:

    TEXT
    UTF-8
    contains python 54%, javascript 40%

---

# Codex handoff transcripts

ClipboardBytes recognizes canonical Codex handoff transcripts as a first-class
clipboard artifact type.

A Codex handoff is classified as `CODEX` before generic text or programming
language inference. The transcript may contain Python, Rust, C, shell commands,
JSON, diffs, tool output, prose, or several of these at once without being
misclassified as `TEXT`, `MIXED`, or an incidental source language.

Canonical handoffs may include a transport identity such as:

    PATH: CODEX:thisrepo:0

and session metadata including repository context.

When Git repository provenance is available, ClipboardBytes carries that
repository identity into its Jarri Clipboard Register integration. This allows
downstream history and provenance tooling to distinguish Codex work by the
repository in which the turn occurred rather than treating every Codex
transcript as anonymous clipboard text.

This is useful for repository-aware development workflows, clipboard history,
Codex session handoff, and causal reconstruction of work across Jarri tools.

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

# Clipboard observation and Jarri provenance

ClipboardBytes distinguishes between two different event semantics.

A real desktop clipboard transition produces a `ClipboardObservation`.

A `ClipboardObservation` contains:

- the classified `ClipboardPayload`;
- the stable content bytes captured at the same observation edge.

Real clipboard transitions emit `observation_ready` before presentation
deduplication.

This signal can feed the Jarri Clipboard Register so that repeated clipboard
content remains distinct in temporal provenance even when its content identity
has appeared before.

Application startup is different.

ClipboardBytes inspects the current clipboard when it starts so that the HUD
can present current state, but startup inspection does not create a provenance
observation because no new clipboard transition occurred.

Presentation also remains independent from provenance.

The HUD may suppress an identical repeated visual state, while every genuine
clipboard transition can still be recorded historically.

Presentation identity includes a SHA-256 digest of captured content, so
different same-sized payloads are not accidentally treated as identical merely
because their kind, MIME type, size, and subtype match.

## Jarri Clipboard Register integration

`jarri_clipboard_register.py` adapts `ClipboardObservation` into the Jarri
Clipboard Register ingest interface:

    /opt/jarri/tools/clipboard-register/clipboard_register.py

The adapter sends the already-captured observation bytes.

It does not reread the live desktop clipboard.

Clipboard Register failures are contained so that provenance persistence
cannot terminate the ClipboardBytes observer or HUD.

The current integration has been exercised with:

- ordinary text;
- repeated identical text;
- same-sized different text;
- browser text;
- file / URI-list clipboard content;
- PNG images;
- Jarri Workspace logical-tab screenshots.

A 5016 × 2088 Workspace PNG of 987204 bytes was observed repeatedly with the
same SHA-256 content identity while retaining separate temporal observations.

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
    ├── jarri_clipboard_register.py
    ├── code_detector.py
    ├── overlay_window.py
    ├── window_manager.py
    ├── config_store.py
    ├── test_clipboard_register_integration.py
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

Stable Linux-first PyQt6 clipboard inspector and developer HUD.

Evolving toward deterministic clipboard inspection, export, history, Codex handoff recognition, Git repository provenance, and explainable classification.

---

# Author

Tor Matz Andrén
