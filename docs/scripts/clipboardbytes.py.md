Title: clipboardbytes.py
Date: 2026-04-24
Updated: 2026-08-17
Author: Matz
Type: script
Subsystem: clipboardbytes
File: clipboardbytes.py

---

# clipboardbytes.py

## Purpose

Application entrypoint and top-level orchestration.

## Responsibilities

- create `QApplication`;
- create `ConfigStore`;
- create `ClipboardSignal`;
- create `WindowManager`;
- create the Jarri Clipboard Register adapter;
- connect provenance observations to the Register adapter;
- connect presentation updates to `WindowManager`;
- perform the initial presentation-only clipboard inspection;
- start the Qt event loop.

## Flow

    QApplication
      ↓
    ClipboardSignal
      ├── observation_ready
      │       ↓
      │   JarriClipboardRegister
      │
      └── payload_changed
              ↓
          WindowManager

Startup then calls:

    ClipboardSignal.refresh()

The initial refresh updates presentation only.

It does not create a provenance observation.

## Ownership

No clipboard classification logic lives in this entrypoint.

No Jarri storage schema logic lives here.

No UI rendering logic lives here.

The file only composes independently owned components.
