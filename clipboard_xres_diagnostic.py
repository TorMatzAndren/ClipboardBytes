#!/usr/bin/env python3
"""Read-only XRes 1.2 probe for current X11 clipboard selection owners.

This opens an X connection, reads selection owner XIDs, and queries XRes.
It never requests clipboard contents or changes selection ownership.
"""

import ctypes
import ctypes.util
import json
import os
import sys


XRES_CLIENT_ID_XID_MASK = 0x01
XRES_CLIENT_ID_PID_MASK = 0x02
X11_SUCCESS = 0


class XResClientIdSpec(ctypes.Structure):
    _fields_ = [("client", ctypes.c_ulong), ("mask", ctypes.c_uint)]


class XResClientIdValue(ctypes.Structure):
    _fields_ = [
        ("spec", XResClientIdSpec),
        ("length", ctypes.c_long),
        ("value", ctypes.c_void_p),
    ]


class XErrorEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("resourceid", ctypes.c_ulong),
        ("serial", ctypes.c_ulong),
        ("error_code", ctypes.c_ubyte),
        ("request_code", ctypes.c_ubyte),
        ("minor_code", ctypes.c_ubyte),
    ]


def main():
    x11_name = ctypes.util.find_library("X11")
    xres_name = ctypes.util.find_library("XRes")
    report = {
        "display": os.environ.get("DISPLAY"),
        "x11_library": x11_name,
        "xres_library": xres_name,
        "struct_layout": {
            "spec_size": ctypes.sizeof(XResClientIdSpec),
            "spec_client_offset": XResClientIdSpec.client.offset,
            "spec_mask_offset": XResClientIdSpec.mask.offset,
            "value_size": ctypes.sizeof(XResClientIdValue),
            "value_length_offset": XResClientIdValue.length.offset,
            "value_pointer_offset": XResClientIdValue.value.offset,
        },
        "x_errors": [],
        "selections": {},
    }
    if not x11_name or not xres_name:
        report["fatal"] = "X11 or XRes shared library not found"
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    x11 = ctypes.CDLL(x11_name)
    xres = ctypes.CDLL(xres_name)
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XSync.restype = ctypes.c_int
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XGetSelectionOwner.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XGetSelectionOwner.restype = ctypes.c_ulong

    xres.XResQueryExtension.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
    ]
    xres.XResQueryExtension.restype = ctypes.c_int
    xres.XResQueryVersion.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
    ]
    xres.XResQueryVersion.restype = ctypes.c_int
    xres.XResQueryClientIds.argtypes = [
        ctypes.c_void_p,
        ctypes.c_long,
        ctypes.POINTER(XResClientIdSpec),
        ctypes.POINTER(ctypes.c_long),
        ctypes.POINTER(ctypes.POINTER(XResClientIdValue)),
    ]
    xres.XResQueryClientIds.restype = ctypes.c_int
    xres.XResClientIdsDestroy.argtypes = [
        ctypes.c_long, ctypes.POINTER(XResClientIdValue)
    ]
    xres.XResClientIdsDestroy.restype = None
    if hasattr(xres, "XResGetClientPid"):
        xres.XResGetClientPid.argtypes = [ctypes.POINTER(XResClientIdValue)]
        xres.XResGetClientPid.restype = ctypes.c_int

    error_handler_type = ctypes.CFUNCTYPE(
        ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(XErrorEvent)
    )

    @error_handler_type
    def on_x_error(_display, event_pointer):
        event = event_pointer.contents
        report["x_errors"].append({
            "error_code": event.error_code,
            "request_code": event.request_code,
            "minor_code": event.minor_code,
            "resource_id": f"0x{event.resourceid:x}",
            "serial": event.serial,
        })
        return 0

    x11.XSetErrorHandler.argtypes = [error_handler_type]
    x11.XSetErrorHandler.restype = ctypes.c_void_p
    display_name = report["display"]
    display = x11.XOpenDisplay(display_name.encode() if display_name else None)
    if not display:
        report["fatal"] = "XOpenDisplay failed"
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    try:
        x11.XSetErrorHandler(on_x_error)
        event_base, error_base = ctypes.c_int(), ctypes.c_int()
        ext_status = xres.XResQueryExtension(
            display, ctypes.byref(event_base), ctypes.byref(error_base)
        )
        major, minor = ctypes.c_int(), ctypes.c_int()
        version_status = (
            xres.XResQueryVersion(display, ctypes.byref(major), ctypes.byref(minor))
            if ext_status else 0
        )
        report["xres_extension"] = {
            "query_extension_return": int(ext_status),
            "event_base": event_base.value,
            "error_base": error_base.value,
            "query_version_return": int(version_status),
            "version": [major.value, minor.value] if version_status else None,
        }

        for selection in ("CLIPBOARD", "CLIPBOARD_MANAGER"):
            atom = x11.XInternAtom(display, selection.encode(), 0)
            window = int(x11.XGetSelectionOwner(display, atom))
            item = {"selection_owner_window": f"0x{window:x}" if window else None,
                    "queries": []}
            report["selections"][selection] = item
            if not window or not version_status or (major.value, minor.value) < (1, 2):
                continue

            # XID mask and PID mask are distinct returned identity types.
            # Probe each separately and together to expose raw server behavior.
            for mask in (XRES_CLIENT_ID_XID_MASK, XRES_CLIENT_ID_PID_MASK,
                         XRES_CLIENT_ID_XID_MASK | XRES_CLIENT_ID_PID_MASK):
                spec = XResClientIdSpec(window, mask)
                count = ctypes.c_long()
                values = ctypes.POINTER(XResClientIdValue)()
                status = xres.XResQueryClientIds(
                    display, 1, ctypes.byref(spec), ctypes.byref(count),
                    ctypes.byref(values)
                )
                # Flush and deliver any protocol error to the installed
                # handler before recording this query's result.
                x11.XSync(display, 0)
                query = {"request_mask": mask, "raw_return": int(status),
                         "success": status == X11_SUCCESS,
                         "num_ids": int(count.value), "returned_ids": []}
                query["x_errors"] = list(report["x_errors"])
                if status == X11_SUCCESS:
                    try:
                        for index in range(max(0, count.value)) if values else ():
                            value = values[index]
                            raw = {"client": int(value.spec.client),
                                   "mask": int(value.spec.mask),
                                   "length": int(value.length),
                                   "value_words": []}
                            if (value.value and value.spec.mask ==
                                    XRES_CLIENT_ID_PID_MASK and value.length == 4):
                                # XRes 1.2 PID values contain one CARD32.
                                # The Xlib API reports length as 4 here.
                                words = 1
                                raw["value_words"] = list(ctypes.cast(
                                    value.value, ctypes.POINTER(ctypes.c_uint32)
                                )[:words])
                                if hasattr(xres, "XResGetClientPid"):
                                    raw["pid"] = int(xres.XResGetClientPid(
                                        ctypes.byref(value)
                                    ))
                            query["returned_ids"].append(raw)
                    finally:
                        xres.XResClientIdsDestroy(count.value, values)
                elif values:
                    xres.XResClientIdsDestroy(count.value, values)
                item["queries"].append(query)
        report["x_errors_after_queries"] = list(report["x_errors"])
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    finally:
        x11.XCloseDisplay(display)


if __name__ == "__main__":
    sys.exit(main())
