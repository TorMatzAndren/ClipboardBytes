Title: config_store.py
Date: 2026-04-24
Author: Matz
Type: script
Subsystem: clipboardbytes
File: config_store.py

---

# config_store.py

## Purpose

Persistence layer.

Stores and restores locked window positions.

---

## Storage Location

    ~/.config/clipboardbytes/state.json

---

## Responsibilities

- Read JSON state
- Validate data structure
- Ignore invalid entries
- Store only locked windows
- Remove unlocked windows
- Clamp restored positions

---

## Data Format

    {
      "version": 1,
      "windows": [
        {
          "id": "...",
          "screen": "...",
          "x": 123,
          "y": 456,
          "locked": true
        }
      ]
    }

---

## Clamp Logic

Ensures window remains partially visible:

- minimum visible width: 40 px
- assumed height: 28 px
- assumed min width: 90 px

---

## Notes

- No UI logic
- No clipboard logic
- Silent failure on corrupted state
- Atomic write via temp file replace
