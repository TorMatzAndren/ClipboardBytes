import hashlib
import traceback

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from clipboard_payload import ClipboardPayloadReader


class ClipboardSignal(QObject):
    observation_ready = pyqtSignal(object)
    payload_changed = pyqtSignal(object)

    def __init__(self, app):
        super().__init__()
        self._clipboard = app.clipboard()
        self._reader = ClipboardPayloadReader()

        self._last_presentation_signature = None

        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.setInterval(120)
        self._delay_timer.timeout.connect(
            self._refresh_observed_change
        )

        self._clipboard.dataChanged.connect(
            self._on_clipboard_changed
        )

    def _on_clipboard_changed(self):
        self._delay_timer.stop()
        self._delay_timer.start()

    def refresh(self):
        """
        Inspect current clipboard state for presentation.

        This is used at application startup and does not create a
        provenance observation.
        """
        observation = self._reader.read_observation(
            self._clipboard
        )
        self._publish_presentation(observation)

    def _refresh_observed_change(self):
        """
        Handle a real debounced QClipboard.dataChanged edge.

        Ordinary acquisition or consumer failures must not escape into Qt's
        timer callback and terminate ClipboardBytes.
        """
        try:
            observation = self._reader.read_observation(
                self._clipboard
            )
        except Exception:
            print(
                "ClipboardBytes observation acquisition failed:",
                flush=True,
            )
            traceback.print_exc()
            return

        try:
            self.observation_ready.emit(observation)
        except Exception:
            print(
                "ClipboardBytes observation consumer failed:",
                flush=True,
            )
            traceback.print_exc()

        try:
            self._publish_presentation(observation)
        except Exception:
            print(
                "ClipboardBytes presentation publication failed:",
                flush=True,
            )
            traceback.print_exc()

    def _publish_presentation(self, observation):
        payload = observation.payload

        signature = (
            payload.kind,
            payload.size_bytes,
            payload.mime_type,
            payload.subtype,
            self._content_digest(observation.content_bytes),
        )

        if signature == self._last_presentation_signature:
            return

        self._last_presentation_signature = signature
        self.payload_changed.emit(payload)

    @staticmethod
    def _content_digest(content):
        if content is None:
            return None

        return hashlib.sha256(content).digest()
