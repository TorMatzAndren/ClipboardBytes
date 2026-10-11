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

Emitted for a `QClipboard.dataChanged` transition except for the confirmed
XFCE persistence-owner handoff described below.

The signal carries a `ClipboardObservation` containing both semantic payload
metadata and the content bytes captured for that observation.

It is emitted before presentation deduplication.

This allows durable provenance to retain repeated clipboard observations.

On X11, a callback is omitted from provenance only when all of these facts
are available: the immediately preceding successful callback came from a
non-manager owner; current ownership is stable across acquisition; the current
clipboard owner is the same live `xfsettingsd` X client that owns the
`CLIPBOARD_MANAGER` selection (confirmed by matching process identities); and
the captured bytes, kind, and MIME type match the previous capture exactly.
X-Resource client PID lookup is preferred, with `_NET_WM_PID` as fallback.
This identifies the XFCE clipboard
persistence handoff. Ownership uncertainty, changed payloads, and transfers
to other applications fail open and remain observations. A new copy from an
application after a handoff remains a distinct observation even if its bytes
match an earlier copy.

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
