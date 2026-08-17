Title: clipboard_payload.py
Date: 2026-08-17
Author: Matz
Type: script
Subsystem: clipboardbytes
File: clipboard_payload.py

---

# clipboard_payload.py

## Purpose

Clipboard acquisition, semantic payload classification, and observation-byte
capture.

## ClipboardPayload

`ClipboardPayload` describes the semantic content selected by ClipboardBytes.

It may contain:

- kind;
- byte count;
- display size;
- MIME type;
- subtype;
- text;
- URLs;
- raw clipboard format names;
- observed copy time.

## ClipboardObservation

`ClipboardObservation` binds:

- one `ClipboardPayload`;
- the stable content bytes captured for that observation.

This keeps semantic metadata and persisted content evidence on the same
acquisition edge.

Downstream provenance consumers therefore do not need to reread a clipboard
whose contents may already have changed.

## Acquisition Priority

The reader currently chooses one primary semantic representation in this
order:

1. image;
2. URL / file list;
3. audio;
4. text;
5. unknown format.

The original clipboard format list is retained as metadata.

This is a version-one semantic projection and does not claim that a native
clipboard event can contain only one representation.

## Content Bytes

Text-like content is preserved as UTF-8 bytes.

File lists are represented as newline-separated URI text.

For binary MIME formats, raw MIME bytes are preferred.

Images fall back to PNG encoding when exact selected MIME bytes are not
available.

If no stable byte representation can be acquired, content bytes may be
unavailable rather than being fabricated.
