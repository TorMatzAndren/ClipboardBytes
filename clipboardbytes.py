#!/usr/bin/env python3

import sys
from PyQt6.QtWidgets import QApplication

from config_store import ConfigStore
from clipboard_signal import ClipboardSignal
from jarri_clipboard_register import JarriClipboardRegister
from window_manager import WindowManager


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ClipboardBytes")
    app.setQuitOnLastWindowClosed(False)

    config = ConfigStore()
    clipboard = ClipboardSignal(app)
    manager = WindowManager(app, config)
    register = JarriClipboardRegister()

    clipboard.observation_ready.connect(
        register.record
    )
    clipboard.payload_changed.connect(manager.update_payload)

    manager.start()
    clipboard.refresh()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
