Title: clipboardbytes.py
Date: 2026-04-24
Author: Matz
Type: script
Subsystem: clipboardbytes
File: clipboardbytes.py

---

# clipboardbytes.py

## Purpose

Application entrypoint.

Initializes the system and starts the Qt event loop.

---

## Responsibilities

- Create QApplication
- Disable quit-on-last-window-close behavior
- Create ConfigStore
- Create ClipboardSignal
- Create WindowManager
- Connect clipboard events to window updates
- Trigger initial clipboard read
- Start Qt event loop

---

## Flow

1. QApplication created
2. ConfigStore initialized
3. ClipboardSignal initialized
4. WindowManager initialized
5. Signal connection:

   clipboard_signal → window_manager.update_clipboard_bytes

6. WindowManager.start()
7. ClipboardSignal.refresh()
8. app.exec()

---

## Notes

- No UI logic exists here
- No clipboard logic exists here
- No persistence logic exists here
- Pure orchestration layer
