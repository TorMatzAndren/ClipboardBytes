#!/usr/bin/env python3

import sys

from PyQt6.QtWidgets import QApplication

from clipboard_signal import ClipboardSignal
from jarri_clipboard_register import JarriClipboardRegister


def main():
    headless = "--headless" in sys.argv[1:]

    qt_argv = [
        argument
        for argument in sys.argv
        if argument != "--headless"
    ]

    app = QApplication(qt_argv)
    app.setApplicationName("ClipboardBytes")
    app.setQuitOnLastWindowClosed(False)

    clipboard = ClipboardSignal(app)
    register = JarriClipboardRegister()

    clipboard.observation_ready.connect(
        register.record
    )

    if not headless:
        from config_store import ConfigStore
        from window_manager import WindowManager

        config = ConfigStore()
        manager = WindowManager(app, config)

        clipboard.payload_changed.connect(
            manager.update_payload
        )

        manager.start()

        # Presentation-only startup inspection. This intentionally does
        # not create a provenance observation.
        clipboard.refresh()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
