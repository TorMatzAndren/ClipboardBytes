Title: jarri_clipboard_register.py
Date: 2026-08-17
Author: Matz
Type: script
Subsystem: clipboardbytes
File: jarri_clipboard_register.py

---

# jarri_clipboard_register.py

## Purpose

ClipboardBytes adapter for the Jarri Clipboard Register.

## Boundary

The adapter receives a completed `ClipboardObservation`.

It forwards the observation's captured bytes and semantic metadata to:

    /opt/jarri/tools/clipboard-register/clipboard_register.py

using its `ingest` command.

ClipboardBytes therefore does not implement or understand the Register's
SQLite schema or content-addressed object-store layout.

## Metadata Forwarded

The adapter currently forwards:

- provider identity `ClipboardBytes`;
- semantic kind;
- MIME type;
- subtype;
- exact captured content bytes.

The Jarri Register owns canonical observation timestamps, SHA-256 identity,
database persistence, and content-object storage.

## Failure Isolation

Register invocation is an external provenance sink.

Ordinary subprocess or operating-system failures are caught and reported.

A provenance persistence failure must not terminate ClipboardBytes or disable
the existing clipboard HUD.

## Current Transport

Version one invokes the Jarri Register through a synchronous local subprocess.

This transport is intentionally considered an implementation detail.

A future persistent local ingest boundary may replace it if latency or runtime
behavior justifies that change.
