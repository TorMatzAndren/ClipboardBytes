import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

import clipboardbytes


class ClipboardBytesStartupTests(unittest.TestCase):
    def test_headless_startup_without_jarri_register(self):
        class TestApplication(QApplication):
            def exec(self):
                QTimer.singleShot(25, self.quit)
                return super().exec()

        with (
            patch.object(clipboardbytes, "QApplication", TestApplication),
            patch.object(
                clipboardbytes,
                "REGISTER",
                Path("/nonexistent/clipboardbytes-test-register"),
            ),
            patch.object(
                clipboardbytes,
                "OrderedClipboardRegisterWriter",
                side_effect=AssertionError(
                    "Register writer must not be constructed"
                ),
            ),
            patch.object(
                sys,
                "argv",
                ["clipboardbytes", "--headless"],
            ),
        ):
            self.assertEqual(clipboardbytes.main(), 0)


if __name__ == "__main__":
    unittest.main()
