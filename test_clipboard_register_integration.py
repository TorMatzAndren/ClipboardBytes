#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from clipboard_payload import ClipboardObservation, ClipboardPayload
from clipboard_signal import ClipboardSignal
from jarri_clipboard_register import JarriClipboardRegister


class DummyConnectSignal:
    def connect(self, callback):
        self.callback = callback


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
        return signal

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

        signal._refresh_observed_change()

        self.assertEqual(provenance, [observed])
        self.assertEqual(len(presentation), 1)

    def test_same_size_different_content_is_not_presentation_duplicate(self):
        signal = self.make_signal(observation(b"cat"))

        presentation = []
        signal.payload_changed.connect(presentation.append)

        signal._refresh_observed_change()

        signal._reader.observation = observation(b"dog")
        signal._refresh_observed_change()

        self.assertEqual(len(presentation), 2)

    def test_repeated_identical_content_still_emits_provenance(self):
        observed = observation(b"cat")
        signal = self.make_signal(observed)

        provenance = []
        presentation = []

        signal.observation_ready.connect(provenance.append)
        signal.payload_changed.connect(presentation.append)

        signal._refresh_observed_change()
        signal._refresh_observed_change()

        self.assertEqual(len(provenance), 2)
        self.assertEqual(len(presentation), 1)

    def test_acquisition_failure_does_not_escape_timer_callback(self):
        signal = self.make_signal(observation(b"unused"))

        def fail(_clipboard):
            raise RuntimeError("synthetic acquisition failure")

        signal._reader.read_observation = fail

        # The failure may be logged, but it must not escape.
        signal._refresh_observed_change()


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


if __name__ == "__main__":
    unittest.main()
