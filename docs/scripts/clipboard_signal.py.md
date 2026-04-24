Title: clipboard_signal.py
Date: 2026-04-24
Author: Matz
Type: script
Subsystem: clipboardbytes
File: clipboard_signal.py

---

# clipboard_signal.py

## Purpose

Clipboard signal layer.

Responsible for detecting clipboard changes and calculating byte size.

---

## Responsibilities

- Access system clipboard via Qt
- Listen to clipboard change events
- Delay clipboard reads slightly
- Read clipboard text
- Compute UTF-8 byte count
- Emit byte_count_changed(text, byte_count)

---

## Byte Counting

Uses UTF-8:

    len(text.encode("utf-8"))

---

## Flow

1. Clipboard emits dataChanged
2. Delay timer starts (~120 ms)
3. Clipboard text read
4. Byte count calculated
5. Signal emitted

---

## Notes

- Prevents duplicate updates using last_text
- No UI logic
- No persistence logic
- Pure signal and transformation layer
