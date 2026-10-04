from __future__ import annotations

import subprocess
import queue
import threading
import traceback
from pathlib import Path


REGISTER = Path(
    "/opt/jarri/tools/clipboard-register/clipboard_register.py"
)


class JarriClipboardRegister:
    def __init__(self, register_path=REGISTER):
        self.register_path = Path(register_path)

    def record(self, observation):
        try:
            return self._record(observation)
        except Exception:
            print(
                "ClipboardBytes Jarri Clipboard Register write failed:",
                flush=True,
            )
            traceback.print_exc()
            return {
                "ok": False,
                "error": "clipboard_register_exception",
            }

    def _record(self, observation):
        payload = observation.payload
        content = observation.content_bytes

        if content is None:
            return {
                "ok": False,
                "error": "no_stable_payload_bytes",
                "kind": payload.kind,
                "mime_type": payload.mime_type,
            }

        command = [
            str(self.register_path),
            "ingest",
            "--provider",
            "ClipboardBytes",
        ]

        if payload.kind:
            command.extend(["--kind", payload.kind])

        if payload.mime_type:
            command.extend(
                ["--mime-type", payload.mime_type]
            )

        if payload.subtype:
            command.extend(["--subtype", payload.subtype])

        if observation.repository_root:
            command.extend(
                ["--repository-root", observation.repository_root]
            )

        if observation.repository_name:
            command.extend(
                ["--repository-name", observation.repository_name]
            )

        process = subprocess.run(
            command,
            input=content,
            capture_output=True,
            timeout=5,
            check=False,
        )

        if process.returncode != 0:
            return {
                "ok": False,
                "error": "clipboard_register_ingest_failed",
                "returncode": process.returncode,
                "stderr": process.stderr.decode(
                    "utf-8",
                    errors="replace",
                ).strip(),
            }

        return {
            "ok": True,
            "stdout": process.stdout.decode(
                "utf-8",
                errors="replace",
            ).strip(),
        }


class OrderedClipboardRegisterWriter:
    """Persist captured observations on one FIFO worker thread."""

    _STOP = object()

    def __init__(self, register):
        self.register = register
        self._queue = queue.Queue()
        self._lock = threading.Lock()
        self._closed = False
        self._thread = threading.Thread(
            target=self._run,
            name="ClipboardBytesRegisterWriter",
            daemon=False,
        )
        self._thread.start()

    def enqueue(self, observation):
        with self._lock:
            if self._closed:
                print(
                    "ClipboardBytes register writer is closed; "
                    "observation was not queued",
                    flush=True,
                )
                return False
            self._queue.put(observation)
            return True

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                self._queue.put(self._STOP)
        self._thread.join()

    def _run(self):
        while True:
            observation = self._queue.get()
            try:
                if observation is self._STOP:
                    return
                result = self.register.record(observation)
                if not result or not result.get("ok"):
                    print(
                        "ClipboardBytes register write failed: "
                        f"{result!r}",
                        flush=True,
                    )
            except Exception:
                print(
                    "ClipboardBytes register writer failed:",
                    flush=True,
                )
                traceback.print_exc()
            finally:
                self._queue.task_done()
