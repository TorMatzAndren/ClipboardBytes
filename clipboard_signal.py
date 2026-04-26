from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from clipboard_payload import ClipboardPayloadReader


class ClipboardSignal(QObject):
    payload_changed = pyqtSignal(object)

    def __init__(self, app):
        super().__init__()
        self._clipboard = app.clipboard()
        self._reader = ClipboardPayloadReader()

        self._last_signature = None

        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.setInterval(120)
        self._delay_timer.timeout.connect(self.refresh)

        self._clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self):
        self._delay_timer.stop()
        self._delay_timer.start()

    def refresh(self):
        payload = self._reader.read(self._clipboard)

        signature = (
            payload.kind,
            payload.size_bytes,
            payload.mime_type,
            payload.subtype,
        )

        if signature == self._last_signature:
            return

        self._last_signature = signature
        self.payload_changed.emit(payload)
