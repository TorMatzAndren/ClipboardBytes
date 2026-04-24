Title: window_manager.py
Date: 2026-04-24
Author: Matz
Type: script
Subsystem: clipboardbytes
File: window_manager.py

---

# window_manager.py

## Purpose

Window lifecycle and coordination layer.

Manages all overlay windows.

---

## Responsibilities

- Create initial window
- Restore locked windows
- Create clones
- Remove windows
- Maintain window list
- Broadcast clipboard updates
- Interface with ConfigStore

---

## Startup Behavior

1. Load saved windows
2. Restore valid locked windows
3. If none restored:
   - create one window on primary screen

---

## Clone Behavior

- Created beside source window
- Not persisted unless locked

---

## Removal Behavior

- Cannot remove last window
- Removes persistence if locked

---

## Update Flow

Receives:

    byte_count_changed(text, byte_count)

Then:

- Updates all active windows

---

## Notes

- No UI rendering logic
- No clipboard access
- Delegates persistence to ConfigStore
