Title: overlay_window.py
Date: 2026-04-24
Author: Matz
Type: script
Subsystem: clipboardbytes
File: overlay_window.py

---

# overlay_window.py

## Purpose

Overlay window UI layer.

Represents a single on-screen window displaying clipboard byte size.

---

## Responsibilities

- Render "<N> bytes"
- Flash green on update
- Restore white text after timer
- Handle right-click menu
- Handle dragging when unlocked
- Maintain lock state
- Request always-on-top behavior
- Avoid keyboard focus

---

## UI Behavior

Normal:

- white text

On update:

- green text for ~2 seconds

---

## Menu

Right-click menu:

- Lock / Unlock
- Add clone
- Remove
- Exit

---

## Dragging

- Enabled when unlocked
- Disabled when locked

---

## Topmost

- Uses Qt window flags
- Reinforced via periodic raise()

---

## Notes

- No clipboard logic
- No persistence logic
- Delegates actions to WindowManager
