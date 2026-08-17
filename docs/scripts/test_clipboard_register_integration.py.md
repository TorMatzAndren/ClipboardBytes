Title: test_clipboard_register_integration.py
Date: 2026-08-17
Author: Matz
Type: test
Subsystem: clipboardbytes
File: test_clipboard_register_integration.py

---

# test_clipboard_register_integration.py

## Purpose

Regression verification for ClipboardBytes clipboard-observation and Jarri
Clipboard Register integration semantics.

## Verified Behavior

The suite verifies that:

- startup inspection does not emit provenance;
- a real clipboard change emits provenance;
- same-sized different content is not a presentation duplicate;
- repeated identical content still emits multiple provenance observations;
- acquisition failure does not escape the Qt callback boundary;
- Register process failure is contained;
- the Register adapter forwards already-captured observation bytes.

## Result

The initial integration checkpoint executed seven tests successfully.

Synthetic failure tests intentionally exercise diagnostic exception paths while
remaining successful tests.
