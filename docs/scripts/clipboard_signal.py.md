Title: clipboard_signal.py
Date: 2026-04-24
Updated: 2026-08-17
Author: Matz
Type: script
Subsystem: clipboardbytes
File: clipboard_signal.py

---

# clipboard_signal.py

## Purpose

Clipboard event and publication layer.

The signal layer separates:

- real clipboard observation;
- startup/current-state inspection;
- human-facing presentation updates.

## Signals

`observation_ready`

Emitted for a real debounced `QClipboard.dataChanged` transition.

The signal carries a `ClipboardObservation` containing both semantic payload
metadata and the content bytes captured for that observation.

It is emitted before presentation deduplication.

This allows durable provenance to retain repeated clipboard observations.

`payload_changed`

Emitted when ClipboardBytes presentation should update.

Presentation deduplication is independent from provenance observation.

## Startup Inspection

`refresh()` reads and presents the current clipboard state.

It intentionally does not emit `observation_ready`.

Starting ClipboardBytes therefore does not manufacture a historical clipboard
event.

## Real Clipboard Change

A real desktop clipboard transition follows:

    QClipboard.dataChanged
      → 120 ms debounce
      → read_observation()
      → observation_ready
      → presentation decision
      → optional payload_changed

## Presentation Identity

Presentation identity includes:

- kind;
- byte count;
- MIME type;
- subtype;
- SHA-256 digest of captured content bytes.

Including content identity prevents same-sized different payloads from being
silently collapsed by the HUD.

Repeated identical content can still be suppressed visually while remaining
separate provenance observations.

## Failure Boundary

Ordinary observation-acquisition, observation-consumer, and presentation
exceptions are contained at the Qt timer callback boundary.

Such failures are reported diagnostically rather than being allowed to escape
into PyQt and terminate the application.

`KeyboardInterrupt` and other `BaseException` subclasses are intentionally not
treated as ordinary runtime failures.
