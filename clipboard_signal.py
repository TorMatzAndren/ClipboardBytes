from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class ClipboardSignal(QObject):
    byte_count_changed = pyqtSignal(str, int)

    def __init__(self, app):
        super().__init__()
        self._clipboard = app.clipboard()
        self._last_text = None

        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.setInterval(120)
        self._delay_timer.timeout.connect(self.refresh)

        self._clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self):
        self._delay_timer.stop()
        self._delay_timer.start()

    def refresh(self):
        text = self._clipboard.text() or ""

        if text == self._last_text:
            byte_count = len(text.encode("utf-8"))
            self.byte_count_changed.emit(text, byte_count)
            return

        self._last_text = text
        byte_count = len(text.encode("utf-8"))
        self.byte_count_changed.emit(text, byte_count)
