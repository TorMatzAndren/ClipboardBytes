#!/usr/bin/env python3

import sys
from os import access, X_OK

from PyQt6.QtWidgets import QApplication

from clipboard_signal import ClipboardSignal
from clipboard_diagnostics import ClipboardDiagnostics
from jarri_clipboard_register import (
    REGISTER,
    JarriClipboardRegister,
    OrderedClipboardRegisterWriter,
)


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

    diagnostics = ClipboardDiagnostics.from_environment()
    clipboard = ClipboardSignal(app, diagnostics=diagnostics)
    # The Jarri Clipboard Register is an optional external integration.
    # Standalone ClipboardBytes must work without it.
    if REGISTER.is_file() and access(REGISTER, X_OK):
        register_writer = OrderedClipboardRegisterWriter(
            JarriClipboardRegister(),
            diagnostics=diagnostics,
        )
        clipboard.observation_ready.connect(
            register_writer.enqueue
        )
        app.aboutToQuit.connect(register_writer.close)
    else:
        register_writer = None

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
