#!/usr/bin/env python3

import sys
from PyQt6.QtWidgets import QApplication

from config_store import ConfigStore
from clipboard_signal import ClipboardSignal
from window_manager import WindowManager


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ClipboardBytes")
    app.setQuitOnLastWindowClosed(False)

    config = ConfigStore()
    clipboard = ClipboardSignal(app)
    manager = WindowManager(app, config)

    clipboard.byte_count_changed.connect(manager.update_clipboard_bytes)

    manager.start()
    clipboard.refresh()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
