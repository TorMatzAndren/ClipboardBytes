#!/usr/bin/env python3

import ctypes
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from clipboard_payload import ClipboardObservation, ClipboardPayload
from clipboard_diagnostics import (
    ClipboardDiagnostics,
    X11ClipboardOwnership,
    _XResClientIdSpec,
    _XResClientIdValue,
    _xres_client_pid,
)
from clipboard_signal import ClipboardSignal
from jarri_clipboard_register import JarriClipboardRegister
from jarri_clipboard_register import OrderedClipboardRegisterWriter


class DummyConnectSignal:
    def connect(self, callback):
        self.callback = callback

    def emit(self):
        self.callback()


class DummyClipboard:
    def __init__(self):
        self.dataChanged = DummyConnectSignal()


class DummyApp:
    def __init__(self):
        self._clipboard = DummyClipboard()

    def clipboard(self):
        return self._clipboard


class FakeReader:
    def __init__(self, observation):
        self.observation = observation
        self.calls = 0

    def read_observation(self, clipboard):
        self.calls += 1
        return self.observation


class FakeTimer:
    def start(self):
        pass


def observation(
    content: bytes,
    *,
    kind="text",
    mime_type="text/plain",
    subtype="UTF-8 · classifier fallback",
    repository_root=None,
    repository_name=None,
):
    return ClipboardObservation(
        payload=ClipboardPayload(
            kind=kind,
            size_bytes=len(content),
            size_label=f"{len(content)} bytes",
            mime_type=mime_type,
            subtype=subtype,
            text=content.decode("utf-8"),
            copied_at="2026-08-17T19:30:00",
        ),
        content_bytes=content,
        repository_root=repository_root,
        repository_name=repository_name,
    )


class ClipboardSignalSemanticsTests(unittest.TestCase):
    def make_signal(self, initial):
        signal = ClipboardSignal(DummyApp())
        signal._reader = FakeReader(initial)
        signal._presentation_timer = FakeTimer()
        return signal

    def run_captures(self, observations, ownership_states):
        signal = ClipboardSignal(DummyApp())

        class SequencedReader:
            def __init__(self):
                self.calls = 0

            def read_observation(self, _clipboard):
                result = observations[self.calls]
                self.calls += 1
                return result

        signal._reader = SequencedReader()
        signal._presentation_timer = FakeTimer()
        captured = []
        signal.observation_ready.connect(captured.append)
        with patch(
            "clipboard_signal.x11_clipboard_ownership",
            side_effect=ownership_states,
        ):
            for _ in observations:
                signal._clipboard.dataChanged.emit()
        return captured

    @staticmethod
    def owner_state(owner, pid, manager="0x20", manager_pid=200):
        return X11ClipboardOwnership(
            clipboard_owner_window=owner,
            clipboard_owner_pid=pid,
            clipboard_manager_window=manager,
            clipboard_manager_pid=manager_pid,
            clipboard_owner_executable=(
                "xfsettingsd" if pid == manager_pid else "source-app"
            ),
            clipboard_owner_pid_source="xres",
            clipboard_manager_pid_source="xres",
        )

    def test_xfsettingsd_persistence_handoff_is_one_observation(self):
        copied = observation(b"same image bytes", kind="image", mime_type="image/png")
        source = self.owner_state("0x10", 100)
        manager = self.owner_state("0x20", 200)

        captured = self.run_captures(
            [copied, copied], [source, source, manager, manager]
        )

        self.assertEqual(captured, [copied])

    def test_missing_manager_property_pid_is_confirmed_by_xres(self):
        copied = observation(
            b"same image bytes", kind="image", mime_type="image/png"
        )
        source = self.owner_state(
            "source-window", 100, manager="manager-window", manager_pid=417
        )
        # X selections can be owned by distinct windows in one process.
        # The manager window has no _NET_WM_PID. XRes resolves the client PID
        # from its X resource ID, confirming the same process as the owner.
        persistence = self.owner_state(
            "owner-window", 417, manager="manager-window", manager_pid=417
        )

        captured = self.run_captures(
            [copied, copied], [source, source, persistence, persistence]
        )

        self.assertEqual(captured, [copied])
        self.assertNotEqual(
            persistence.clipboard_owner_window,
            persistence.clipboard_manager_window,
        )
        self.assertEqual(
            persistence.clipboard_owner_pid,
            persistence.clipboard_manager_pid,
        )
        self.assertTrue(persistence.is_xfce_persistence_owner)

    def test_missing_manager_pid_without_xres_identity_fails_open(self):
        copied = observation(
            b"same image bytes", kind="image", mime_type="image/png"
        )
        source = self.owner_state(
            "source-window", 100, manager="manager-window", manager_pid=417
        )
        unconfirmed = X11ClipboardOwnership(
            clipboard_owner_window="owner-window",
            clipboard_owner_pid=417,
            clipboard_manager_window="manager-window",
            clipboard_manager_pid=None,
            clipboard_owner_executable="xfsettingsd",
            clipboard_owner_pid_source="xres",
            clipboard_manager_pid_source=None,
        )

        captured = self.run_captures(
            [copied, copied], [source, source, unconfirmed, unconfirmed]
        )

        self.assertEqual(captured, [copied, copied])

    def test_xres_success_status_resolves_resource_client_pid(self):
        class FakeXRes:
            def __init__(self):
                self.pid = (ctypes.c_uint32 * 1)(731)
                self.value = _XResClientIdValue(
                    spec=_XResClientIdSpec(0x1234, 2),
                    # XRes 1.2 returns one PID CARD32; Xlib length is 4.
                    length=ctypes.sizeof(ctypes.c_uint32),
                    value=ctypes.cast(self.pid, ctypes.c_void_p),
                )
                self.values = (_XResClientIdValue * 1)(self.value)
                self.destroyed = False

            def XResQueryClientIds(
                self, _display, _spec_count, _spec, num_ids, client_ids
            ):
                ctypes.cast(num_ids, ctypes.POINTER(ctypes.c_long))[0] = 1
                ctypes.cast(
                    client_ids,
                    ctypes.POINTER(ctypes.POINTER(_XResClientIdValue)),
                )[0] = ctypes.cast(
                    self.values, ctypes.POINTER(_XResClientIdValue)
                )
                return 0  # X11 Success is zero.

            def XResGetClientPid(self, value_pointer):
                value = ctypes.cast(
                    value_pointer, ctypes.POINTER(_XResClientIdValue)
                )[0]
                return ctypes.cast(
                    value.value, ctypes.POINTER(ctypes.c_uint32)
                )[0]

            def XResClientIdsDestroy(self, _count, _client_ids):
                self.destroyed = True

        xres = FakeXRes()

        pid, resolution = _xres_client_pid(xres, object(), 0x1234)

        self.assertEqual(pid, 731)
        self.assertEqual(resolution, "xres_resolved")
        self.assertTrue(xres.destroyed)

    def test_xres_uses_pid_mask_and_xlib_byte_length(self):
        class FakeXRes:
            def __init__(self, length):
                self.pid = (ctypes.c_uint32 * 1)(731)
                self.value = _XResClientIdValue(
                    spec=_XResClientIdSpec(0x1234, 2),
                    length=length,
                    value=ctypes.cast(self.pid, ctypes.c_void_p),
                )
                self.values = (_XResClientIdValue * 1)(self.value)
                self.request_mask = None

            def XResQueryClientIds(
                self, _display, _count, spec_pointer, num_ids, client_ids
            ):
                self.request_mask = ctypes.cast(
                    spec_pointer, ctypes.POINTER(_XResClientIdSpec)
                )[0].mask
                ctypes.cast(num_ids, ctypes.POINTER(ctypes.c_long))[0] = 1
                ctypes.cast(
                    client_ids,
                    ctypes.POINTER(ctypes.POINTER(_XResClientIdValue)),
                )[0] = ctypes.cast(
                    self.values, ctypes.POINTER(_XResClientIdValue)
                )
                return 0

            def XResClientIdsDestroy(self, _count, _client_ids):
                pass

        self.assertEqual(_XResClientIdSpec.client.offset, 0)
        self.assertEqual(_XResClientIdSpec.mask.offset, ctypes.sizeof(ctypes.c_ulong))
        self.assertEqual(
            _XResClientIdValue.length.offset,
            ctypes.sizeof(_XResClientIdSpec),
        )
        valid = FakeXRes(ctypes.sizeof(ctypes.c_uint32))
        self.assertEqual(_xres_client_pid(valid, object(), 0x1234),
                         (731, "xres_resolved"))
        self.assertEqual(valid.request_mask, 2)  # XRES_CLIENT_ID_PID_MASK

        # XRes PID result length is 4 in the public Xlib API.
        invalid_length = FakeXRes(1)
        self.assertEqual(
            _xres_client_pid(invalid_length, object(), 0x1234),
            (None, "resource_identity_missing"),
        )

    def test_xres_query_error_and_missing_resource_identity_are_distinct(self):
        class QueryFailure:
            def XResQueryClientIds(
                self, _display, _spec_count, _spec, _num_ids, _client_ids
            ):
                return 1  # Positive X11 error status is not Success.

        class MissingIdentity:
            def XResQueryClientIds(
                self, _display, _spec_count, _spec, num_ids, client_ids
            ):
                ctypes.cast(num_ids, ctypes.POINTER(ctypes.c_long))[0] = 0
                ctypes.cast(
                    client_ids,
                    ctypes.POINTER(ctypes.POINTER(_XResClientIdValue)),
                )[0] = ctypes.POINTER(_XResClientIdValue)()
                self.destroyed = False
                return 0

            def XResClientIdsDestroy(self, _count, _client_ids):
                self.destroyed = True

        class ImplementationError:
            def XResQueryClientIds(
                self, _display, _spec_count, _spec, _num_ids, _client_ids
            ):
                raise AttributeError("missing XRes symbol")

        self.assertEqual(
            _xres_client_pid(QueryFailure(), object(), 0x1234),
            (None, "query_failed"),
        )
        self.assertEqual(
            _xres_client_pid(MissingIdentity(), object(), 0x1234),
            (None, "resource_identity_missing"),
        )
        self.assertEqual(
            _xres_client_pid(ImplementationError(), object(), 0x1234),
            (None, "implementation_error:AttributeError"),
        )

    def test_xres_empty_success_is_success_and_destroyed(self):
        class EmptySuccess:
            def XResQueryClientIds(
                self, _display, _spec_count, _spec, num_ids, client_ids
            ):
                ctypes.cast(num_ids, ctypes.POINTER(ctypes.c_long))[0] = 0
                ctypes.cast(
                    client_ids,
                    ctypes.POINTER(ctypes.POINTER(_XResClientIdValue)),
                )[0] = ctypes.POINTER(_XResClientIdValue)()
                return 0

            def XResClientIdsDestroy(self, count, client_ids):
                self.destroyed = (count, bool(client_ids))

        result = EmptySuccess()
        self.assertEqual(
            _xres_client_pid(result, object(), 0x1234),
            (None, "resource_identity_missing"),
        )
        self.assertEqual(result.destroyed, (0, False))

    def test_changed_payload_on_xfsettingsd_owner_is_preserved(self):
        original = observation(b"image A", kind="image", mime_type="image/png")
        changed = observation(b"image B", kind="image", mime_type="image/png")
        source = self.owner_state("0x10", 100)
        manager = self.owner_state("0x20", 200)

        captured = self.run_captures(
            [original, changed], [source, source, manager, manager]
        )

        self.assertEqual(captured, [original, changed])

    def test_two_identical_deliberate_copies_are_preserved(self):
        copied = observation(b"same image bytes", kind="image", mime_type="image/png")
        source = self.owner_state("0x10", 100)
        manager = self.owner_state("0x20", 200)

        captured = self.run_captures(
            [copied, copied, copied, copied],
            [source, source, manager, manager] * 2,
        )

        self.assertEqual(captured, [copied, copied])

    def test_delayed_owner_handoffs_preserve_separate_identical_copies(self):
        screenshot = observation(
            b"same screenshot bytes", kind="image", mime_type="image/png"
        )
        source = self.owner_state("source-window", 100)
        manager = self.owner_state("manager-window", 200)

        # Each screenshot creates a source-owner callback followed by the
        # manager handoff. The first callback's acquisition can straddle the
        # handoff; no callback-time threshold is involved.
        states = [
            source, manager,
            manager, manager,
            source, manager,
            manager, manager,
        ]
        captured = self.run_captures(
            [screenshot, screenshot, screenshot, screenshot], states
        )

        self.assertEqual(captured, [screenshot, screenshot])

    def test_identical_content_from_another_application_is_preserved(self):
        copied = observation(b"same image bytes", kind="image", mime_type="image/png")
        source = self.owner_state("0x10", 100)
        other = self.owner_state("0x30", 300)

        captured = self.run_captures(
            [copied, copied], [source, source, other, other]
        )

        self.assertEqual(captured, [copied, copied])

    def test_unknown_ownership_metadata_fails_open(self):
        copied = observation(b"same image bytes", kind="image", mime_type="image/png")
        source = self.owner_state("0x10", 100)
        unknown = X11ClipboardOwnership(None, None, None, None, None)

        captured = self.run_captures(
            [copied, copied], [source, source, unknown, unknown]
        )

        self.assertEqual(captured, [copied, copied])

    def test_unconfirmed_manager_process_fails_open(self):
        copied = observation(
            b"same image bytes", kind="image", mime_type="image/png"
        )
        source = self.owner_state("0x10", 100)
        unknown_manager = X11ClipboardOwnership(
            clipboard_owner_window="0x20",
            clipboard_owner_pid=200,
            clipboard_manager_window="0x20",
            clipboard_manager_pid=200,
            clipboard_owner_executable="other-daemon",
        )

        captured = self.run_captures(
            [copied, copied], [source, source, unknown_manager, unknown_manager]
        )

        self.assertEqual(captured, [copied, copied])

    def test_unknown_previous_owner_fails_open(self):
        copied = observation(
            b"same image bytes", kind="image", mime_type="image/png"
        )
        unknown = X11ClipboardOwnership(
            clipboard_owner_window=None,
            clipboard_owner_pid=None,
            clipboard_manager_window="0x20",
            clipboard_manager_pid=200,
            clipboard_owner_executable=None,
        )
        manager = self.owner_state("0x20", 200)

        captured = self.run_captures(
            [copied, copied], [unknown, unknown, manager, manager]
        )

        self.assertEqual(captured, [copied, copied])

    def test_startup_refresh_does_not_emit_provenance_observation(self):
        signal = self.make_signal(observation(b"startup"))

        provenance = []
        presentation = []

        signal.observation_ready.connect(provenance.append)
        signal.payload_changed.connect(presentation.append)

        signal.refresh()

        self.assertEqual(provenance, [])
        self.assertEqual(len(presentation), 1)

    def test_real_change_emits_provenance_observation(self):
        observed = observation(b"cat")
        signal = self.make_signal(observed)

        provenance = []
        presentation = []

        signal.observation_ready.connect(provenance.append)
        signal.payload_changed.connect(presentation.append)

        signal._clipboard.dataChanged.emit()
        signal._publish_pending_presentation()

        self.assertEqual(provenance, [observed])
        self.assertEqual(len(presentation), 1)

    def test_same_size_different_content_is_not_presentation_duplicate(self):
        signal = self.make_signal(observation(b"cat"))

        presentation = []
        signal.payload_changed.connect(presentation.append)

        signal._clipboard.dataChanged.emit()
        signal._publish_pending_presentation()

        signal._reader.observation = observation(b"dog")
        signal._clipboard.dataChanged.emit()
        signal._publish_pending_presentation()

        self.assertEqual(len(presentation), 2)

    def test_repeated_identical_content_still_emits_provenance(self):
        observed = observation(b"cat")
        signal = self.make_signal(observed)

        provenance = []
        presentation = []

        signal.observation_ready.connect(provenance.append)
        signal.payload_changed.connect(presentation.append)

        signal._clipboard.dataChanged.emit()
        signal._clipboard.dataChanged.emit()
        signal._publish_pending_presentation()

        self.assertEqual(len(provenance), 2)
        self.assertEqual(len(presentation), 1)

    def test_changes_within_debounce_interval_each_capture_observation(self):
        first = observation(b"first")
        second = observation(b"second")
        signal = self.make_signal(first)
        provenance = []
        signal.observation_ready.connect(provenance.append)

        signal._clipboard.dataChanged.emit()
        signal._reader.observation = second
        signal._clipboard.dataChanged.emit()

        self.assertEqual(provenance, [first, second])

    def test_enabled_diagnostics_preserve_single_observation_ingestion(self):
        stream = io.StringIO()
        diagnostics = ClipboardDiagnostics(enabled=True, stream=stream)
        observed = observation(b"private clipboard payload")
        signal = ClipboardSignal(DummyApp(), diagnostics=diagnostics)
        signal._reader = FakeReader(observed)
        signal._presentation_timer = FakeTimer()
        recorded = []

        class Register:
            def record(self, item):
                recorded.append(item)
                return {"ok": True, "stdout": '{"observation_id": 7}'}

        writer = OrderedClipboardRegisterWriter(
            Register(), diagnostics=diagnostics
        )
        signal.observation_ready.connect(writer.enqueue)

        state = self.owner_state("0x42", 42)
        with patch(
            "clipboard_signal.x11_clipboard_ownership",
            return_value=state,
        ):
            signal._clipboard.dataChanged.emit()
        writer._queue.join()
        writer.close()

        self.assertEqual(recorded, [observed.__class__(
            payload=observed.payload,
            content_bytes=observed.content_bytes,
            repository_root=observed.repository_root,
            repository_name=observed.repository_name,
            diagnostic_sequence=1,
        )])
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(
            [event["event"] for event in events],
            [
                "clipboard_callback",
                "clipboard_acquisition_complete",
                "observation_enqueue",
                "register_write_complete",
            ],
        )
        self.assertEqual([event["sequence"] for event in events], [1, 1, 1, 1])
        self.assertEqual(
            events[0]["x11_ownership_before"]["clipboard_owner_window"],
            "0x42",
        )
        self.assertEqual(
            events[1]["x11_ownership_after"]["clipboard_owner_window"],
            "0x42",
        )
        self.assertNotIn("private clipboard payload", stream.getvalue())
        self.assertEqual(events[-1]["observation_id"], 7)

    def test_acquisition_failure_does_not_escape_timer_callback(self):
        signal = self.make_signal(observation(b"unused"))

        def fail(_clipboard):
            raise RuntimeError("synthetic acquisition failure")

        signal._reader.read_observation = fail

        # The failure may be logged, but it must not escape the Qt callback.
        signal._clipboard.dataChanged.emit()


class ClipboardRegisterAdapterTests(unittest.TestCase):
    def test_register_process_failure_is_contained(self):
        adapter = JarriClipboardRegister(
            register_path=Path(
                "/definitely/not/a/real/clipboard-register"
            )
        )

        result = adapter.record(observation(b"test"))

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["error"],
            "clipboard_register_exception",
        )

    def test_adapter_forwards_repository_provenance(self):
        with tempfile.TemporaryDirectory() as tempdir:
            wrapper = Path(tempdir) / "wrapper.py"
            output = Path(tempdir) / "args.txt"

            wrapper.write_text(
                f"""#!/usr/bin/env python3
import pathlib
import sys

pathlib.Path({str(output)!r}).write_text(
    "\\n".join(sys.argv[1:])
)
sys.stdin.buffer.read()
"""
            )
            wrapper.chmod(0o755)

            adapter = JarriClipboardRegister(
                register_path=wrapper
            )

            result = adapter.record(
                observation(
                    b"codex",
                    kind="codex",
                    mime_type="text/x-codex-handoff",
                    subtype="Codex handoff",
                    repository_root="/home/test/project",
                    repository_name="project",
                )
            )

            self.assertTrue(result["ok"])

            args = output.read_text().splitlines()
            self.assertIn("--repository-root", args)
            self.assertIn("/home/test/project", args)
            self.assertIn("--repository-name", args)
            self.assertIn("project", args)

    def test_adapter_passes_captured_bytes_not_live_clipboard(self):
        with tempfile.TemporaryDirectory() as tempdir:
            fake_register = Path(tempdir) / "register.py"
            output = Path(tempdir) / "captured.bin"

            fake_register.write_text(
                """#!/usr/bin/env python3
import pathlib
import sys

data = sys.stdin.buffer.read()
pathlib.Path(sys.argv[1]).write_bytes(data)
"""
            )
            fake_register.chmod(0o755)

            # The production adapter adds CLI arguments, so use a tiny
            # wrapper that ignores them and records stdin.
            wrapper = Path(tempdir) / "wrapper.py"
            wrapper.write_text(
                f"""#!/usr/bin/env python3
import pathlib
import sys

data = sys.stdin.buffer.read()
pathlib.Path({str(output)!r}).write_bytes(data)
"""
            )
            wrapper.chmod(0o755)

            adapter = JarriClipboardRegister(
                register_path=wrapper
            )

            captured = observation(b"captured-at-observation-edge")
            result = adapter.record(captured)

            self.assertTrue(result["ok"])
            self.assertEqual(
                output.read_bytes(),
                b"captured-at-observation-edge",
            )


class OrderedClipboardRegisterWriterTests(unittest.TestCase):
    def test_slow_register_does_not_block_acquisition_or_drop_next_item(self):
        started = threading.Event()
        release = threading.Event()
        completed = []

        class SlowRegister:
            def record(self, item):
                if item.payload.text == "first":
                    started.set()
                    release.wait(2)
                completed.append(item.payload.text)
                return {"ok": True}

        writer = OrderedClipboardRegisterWriter(SlowRegister())
        signal = ClipboardSignal(DummyApp())
        signal._reader = FakeReader(observation(b"first"))
        signal._presentation_timer = FakeTimer()
        signal.observation_ready.connect(writer.enqueue)
        try:
            signal._clipboard.dataChanged.emit()
            self.assertTrue(started.wait(1))

            second = observation(b"second")
            signal._reader.observation = second
            signal._clipboard.dataChanged.emit()
            self.assertEqual(signal._reader.calls, 2)
            self.assertEqual(signal._pending_presentation, second)
        finally:
            release.set()
            writer.close()

        self.assertEqual(completed, ["first", "second"])

    def test_register_failures_are_contained_and_writer_continues(self):
        recorded = []

        class FailingRegister:
            def record(self, item):
                if item.payload.text == "first":
                    raise RuntimeError("synthetic register failure")
                recorded.append(item.payload.text)
                return {"ok": True}

        writer = OrderedClipboardRegisterWriter(FailingRegister())
        writer.enqueue(observation(b"first"))
        writer.enqueue(observation(b"second"))
        writer.close()
        self.assertEqual(recorded, ["second"])


if __name__ == "__main__":
    unittest.main()
