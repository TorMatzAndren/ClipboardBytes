"""Opt-in, payload-safe event tracing for clipboard investigations."""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


_X11_SUCCESS = 0


class ClipboardDiagnostics:
    """Emit JSON Lines diagnostics to stderr when explicitly enabled."""

    def __init__(self, enabled: bool = False, stream=None):
        self.enabled = enabled
        self.stream = stream or sys.stderr
        self._lock = threading.Lock()
        self._sequence = 0

    @classmethod
    def from_environment(cls):
        enabled = os.environ.get("CLIPBOARDBYTES_DIAGNOSTICS", "")
        return cls(enabled.strip().lower() in {"1", "true", "yes", "on"})

    def next_sequence(self) -> int | None:
        if not self.enabled:
            return None
        with self._lock:
            self._sequence += 1
            return self._sequence

    def record(self, event: str, **fields):
        if not self.enabled:
            return

        entry = {
            "event": event,
            "monotonic_ns": time.monotonic_ns(),
            "wall_time_utc": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "thread_id": threading.get_ident(),
            "thread_name": threading.current_thread().name,
            **fields,
        }
        try:
            line = json.dumps(entry, ensure_ascii=True, sort_keys=True)
            with self._lock:
                self.stream.write(line + "\n")
                self.stream.flush()
        except Exception:
            # Diagnostics must never interfere with clipboard capture.
            return


@dataclass(frozen=True)
class X11ClipboardOwnership:
    clipboard_owner_window: str | None
    clipboard_owner_pid: int | None
    clipboard_manager_window: str | None
    clipboard_manager_pid: int | None
    clipboard_owner_executable: str | None
    clipboard_owner_pid_source: str | None = None
    clipboard_manager_pid_source: str | None = None
    xres_library_status: str | None = None
    xres_extension_status: str | None = None
    clipboard_owner_pid_resolution: str | None = None
    clipboard_manager_pid_resolution: str | None = None

    @property
    def is_xfce_persistence_owner(self):
        return bool(
            self.clipboard_owner_window
            and self.clipboard_manager_window
            and self.clipboard_owner_pid is not None
            and self.clipboard_owner_pid == self.clipboard_manager_pid
            and self.clipboard_owner_pid_source is not None
            and self.clipboard_owner_pid_source
            == self.clipboard_manager_pid_source
            and self.clipboard_owner_executable == "xfsettingsd"
        )

    def to_dict(self):
        result = asdict(self)
        result["is_xfce_persistence_owner"] = (
            self.is_xfce_persistence_owner
        )
        return result


def _process_executable(pid):
    if pid is None:
        return None
    try:
        name = Path(os.readlink(f"/proc/{pid}/exe")).name
    except OSError:
        return None
    suffix = " (deleted)"
    return name.removesuffix(suffix)


class _XResClientIdSpec(ctypes.Structure):
    _fields_ = [("client", ctypes.c_ulong), ("mask", ctypes.c_uint)]


class _XResClientIdValue(ctypes.Structure):
    _fields_ = [
        ("spec", _XResClientIdSpec),
        ("length", ctypes.c_long),
        ("value", ctypes.c_void_p),
    ]


def _xres_client_pid(xres, display, window):
    """Return (PID, status) for a local X resource client identity."""
    spec = _XResClientIdSpec(int(window), 2)  # XRES_CLIENT_ID_PID_MASK
    count = ctypes.c_long()
    values = ctypes.POINTER(_XResClientIdValue)()
    query_returned = False
    try:
        status = xres.XResQueryClientIds(
            display,
            1,
            ctypes.byref(spec),
            ctypes.byref(count),
            ctypes.byref(values),
        )
        query_returned = True
        # This API returns the X11 Status value: Success is zero.
        if status != _X11_SUCCESS:
            return None, "query_failed"
        if count.value <= 0 or not values:
            return None, "resource_identity_missing"
        for index in range(count.value):
            entry = values[index]
            if (
                entry.spec.mask == 2
                # Xlib's public XResClientIdValue.length is a byte count,
                # although the wire protocol encodes it as CARD32 units.
                and entry.length == ctypes.sizeof(ctypes.c_uint32)
                and entry.value
            ):
                get_pid = getattr(xres, "XResGetClientPid", None)
                if get_pid is not None:
                    pid = get_pid(ctypes.byref(entry))
                else:
                    # Compatibility with libXRes builds lacking this helper.
                    pid = ctypes.cast(
                        entry.value,
                        ctypes.POINTER(ctypes.c_uint32),
                    )[0]
                if pid:
                    return int(pid), "xres_resolved"
        return None, "resource_identity_missing"
    except Exception as exc:
        return None, f"implementation_error:{type(exc).__name__}"
    finally:
        if query_returned or values:
            try:
                xres.XResClientIdsDestroy(count.value, values)
            except Exception:
                pass


def x11_clipboard_ownership():
    """Read live CLIPBOARD and CLIPBOARD_MANAGER owner identities."""
    display_name = os.environ.get("DISPLAY")
    library_name = ctypes.util.find_library("X11")
    if not display_name or not library_name:
        return None

    try:
        x11 = ctypes.CDLL(library_name)
        try:
            xres_name = ctypes.util.find_library("XRes")
        except Exception as exc:
            xres_name = None
            xres_library_status = (
                f"library_discovery_error:{type(exc).__name__}"
            )
        else:
            xres_library_status = "library_not_found"
        xres = None
        if xres_name:
            try:
                xres = ctypes.CDLL(xres_name)
                xres_library_status = f"loaded:{xres_name}"
            except OSError as exc:
                xres_library_status = f"library_load_error:{exc.__class__.__name__}"
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XGetSelectionOwner.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XGetSelectionOwner.restype = ctypes.c_ulong
        x11.XGetWindowProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_long,
            ctypes.c_long,
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        x11.XGetWindowProperty.restype = ctypes.c_int
        x11.XFree.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = x11.XOpenDisplay(display_name.encode())
        if not display:
            return None
        try:
            clipboard_atom = x11.XInternAtom(display, b"CLIPBOARD", 0)
            manager_atom = x11.XInternAtom(
                display, b"CLIPBOARD_MANAGER", 0
            )
            clipboard_owner = x11.XGetSelectionOwner(
                display, clipboard_atom
            )
            manager_owner = x11.XGetSelectionOwner(display, manager_atom)
            pid_atom = x11.XInternAtom(display, b"_NET_WM_PID", 0)
            cardinal_atom = x11.XInternAtom(display, b"CARDINAL", 0)

            xres_ready = False
            xres_extension_status = "library_unavailable"
            if xres is not None:
                try:
                    xres.XResQueryExtension.argtypes = [
                        ctypes.c_void_p,
                        ctypes.POINTER(ctypes.c_int),
                        ctypes.POINTER(ctypes.c_int),
                    ]
                    xres.XResQueryExtension.restype = ctypes.c_int
                    xres.XResQueryVersion.argtypes = [
                        ctypes.c_void_p,
                        ctypes.POINTER(ctypes.c_int),
                        ctypes.POINTER(ctypes.c_int),
                    ]
                    xres.XResQueryVersion.restype = ctypes.c_int
                    xres.XResQueryClientIds.argtypes = [
                        ctypes.c_void_p,
                        ctypes.c_long,
                        ctypes.POINTER(_XResClientIdSpec),
                        ctypes.POINTER(ctypes.c_long),
                        ctypes.POINTER(ctypes.POINTER(_XResClientIdValue)),
                    ]
                    xres.XResQueryClientIds.restype = ctypes.c_int
                    xres.XResClientIdsDestroy.argtypes = [
                        ctypes.c_long,
                        ctypes.POINTER(_XResClientIdValue),
                    ]
                    if hasattr(xres, "XResGetClientPid"):
                        xres.XResGetClientPid.argtypes = [
                            ctypes.POINTER(_XResClientIdValue)
                        ]
                        xres.XResGetClientPid.restype = ctypes.c_int
                    event_base = ctypes.c_int()
                    error_base = ctypes.c_int()
                    major = ctypes.c_int()
                    minor = ctypes.c_int()
                    if not xres.XResQueryExtension(
                            display,
                            ctypes.byref(event_base),
                            ctypes.byref(error_base),
                        ):
                        xres_extension_status = "extension_unavailable"
                    elif not xres.XResQueryVersion(
                            display,
                            ctypes.byref(major),
                            ctypes.byref(minor),
                        ):
                        xres_extension_status = "version_query_failed"
                    elif (major.value, minor.value) < (1, 2):
                        xres_extension_status = (
                            f"unsupported_version:{major.value}.{minor.value}"
                        )
                    else:
                        xres_ready = True
                        xres_extension_status = (
                            f"supported:{major.value}.{minor.value}"
                        )
                except Exception as exc:
                    xres_ready = False
                    xres_extension_status = (
                        f"implementation_error:{type(exc).__name__}"
                    )

            def xres_window_pid(window):
                if not window or not xres_ready:
                    return None, xres_extension_status
                return _xres_client_pid(xres, display, window)

            def window_pid(window):
                if not window:
                    return None, None, "selection_unowned"
                pid, resolution = xres_window_pid(window)
                if pid is not None:
                    return pid, "xres", resolution
                actual_type = ctypes.c_ulong()
                actual_format = ctypes.c_int()
                item_count = ctypes.c_ulong()
                bytes_after = ctypes.c_ulong()
                property_data = ctypes.c_void_p()
                status = x11.XGetWindowProperty(
                    display,
                    window,
                    pid_atom,
                    0,
                    1,
                    0,
                    0,
                    ctypes.byref(actual_type),
                    ctypes.byref(actual_format),
                    ctypes.byref(item_count),
                    ctypes.byref(bytes_after),
                    ctypes.byref(property_data),
                )
                try:
                    if (
                        status != 0
                        or actual_type.value != cardinal_atom
                        or actual_format.value != 32
                        or item_count.value < 1
                        or not property_data.value
                    ):
                        return None, None, f"{resolution};net_wm_pid_missing"
                    # Xlib represents format-32 property items as C longs.
                    pid = ctypes.cast(
                        property_data,
                        ctypes.POINTER(ctypes.c_ulong),
                    )[0]
                    if pid:
                        return int(pid), "net_wm_pid", f"{resolution};net_wm_pid_resolved"
                    return None, None, f"{resolution};net_wm_pid_missing"
                finally:
                    if property_data.value:
                        x11.XFree(property_data)

            clipboard_pid, clipboard_pid_source, clipboard_pid_resolution = (
                window_pid(clipboard_owner)
            )
            manager_pid, manager_pid_source, manager_pid_resolution = (
                window_pid(manager_owner)
            )
            return X11ClipboardOwnership(
                clipboard_owner_window=(
                    f"0x{clipboard_owner:x}" if clipboard_owner else None
                ),
                clipboard_owner_pid=clipboard_pid,
                clipboard_manager_window=(
                    f"0x{manager_owner:x}" if manager_owner else None
                ),
                clipboard_manager_pid=manager_pid,
                clipboard_owner_executable=_process_executable(
                    clipboard_pid
                ),
                clipboard_owner_pid_source=clipboard_pid_source,
                clipboard_manager_pid_source=manager_pid_source,
                xres_library_status=xres_library_status,
                xres_extension_status=xres_extension_status,
                clipboard_owner_pid_resolution=clipboard_pid_resolution,
                clipboard_manager_pid_resolution=manager_pid_resolution,
            )
        finally:
            x11.XCloseDisplay(display)
    except Exception:
        return None


def x11_clipboard_owner():
    """Compatibility helper returning only the CLIPBOARD window ID."""
    ownership = x11_clipboard_ownership()
    return ownership.clipboard_owner_window if ownership else None
