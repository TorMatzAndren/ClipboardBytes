import uuid

from PyQt6.QtWidgets import QFileDialog

from clipboard_exporter import ClipboardExporter
from overlay_window import OverlayWindow


class WindowManager:
    DEFAULT_MARGIN_X = 20
    DEFAULT_MARGIN_Y = 20

    def __init__(self, app, config_store):
        self.app = app
        self.config_store = config_store
        self.settings = self.config_store.load_settings()

        self.exporter = ClipboardExporter(
            export_dir=self.settings["export_dir"],
            write_metadata_json=self.settings["write_metadata_json"],
        )

        self.windows = []
        self.current_payload = None

    def start(self):
        screens = self.app.screens()
        saved_windows = self.config_store.load_windows(screens)

        for saved in saved_windows:
            screen = self._find_screen(saved["screen"])
            if screen is None:
                continue

            geometry = screen.availableGeometry()

            x, y = self.config_store.clamp_position(
                saved["x"],
                saved["y"],
                geometry,
                window_width=150,
                window_height=98,
            )

            window = self._create_window(
                screen_name=saved["screen"],
                window_id=saved["id"],
                locked=True,
                x=x,
                y=y,
            )
            window.show()
            window.force_topmost()

        if not self.windows:
            primary_screen = self.app.primaryScreen()
            geometry = primary_screen.availableGeometry()

            x = geometry.right() - 150 - self.DEFAULT_MARGIN_X
            y = geometry.bottom() - 98 - self.DEFAULT_MARGIN_Y

            x, y = self.config_store.clamp_position(
                x,
                y,
                geometry,
                window_width=150,
                window_height=98,
            )

            window = self._create_window(
                screen_name=primary_screen.name(),
                window_id=self._new_id(),
                locked=False,
                x=x,
                y=y,
            )
            window.show()
            window.force_topmost()

    def update_payload(self, payload):
        self.current_payload = payload

        for window in list(self.windows):
            window.set_payload(payload)

    def export_current_payload(self):
        if self.current_payload is None:
            self._broadcast_save_status(ok=False, message="nothing to save")
            return

        try:
            result = self.exporter.export_payload(
                self.current_payload,
                self.app.clipboard(),
            )
        except Exception as exc:
            self._broadcast_save_status(ok=False, message=f"save error: {exc}")
            return

        self._broadcast_save_status(
            ok=bool(result.get("ok")),
            message=result.get("message", "saved" if result.get("ok") else "save failed"),
        )

    def open_export_folder(self):
        try:
            self.exporter.open_export_folder()
        except Exception as exc:
            self._broadcast_save_status(ok=False, message=f"open error: {exc}")
            return

        self._broadcast_save_status(ok=True, message="folder opened")

    def choose_export_folder(self, parent=None):
        selected = QFileDialog.getExistingDirectory(
            parent,
            "Choose ClipboardBytes export folder",
            self.settings["export_dir"],
        )

        if not selected:
            return

        self.settings["export_dir"] = selected
        self._save_settings()
        self._broadcast_save_status(ok=True, message="export folder set")

    def toggle_metadata_json(self):
        self.settings["write_metadata_json"] = not self.settings["write_metadata_json"]
        self._save_settings()

        state = "on" if self.settings["write_metadata_json"] else "off"
        self._broadcast_save_status(ok=True, message=f"metadata json {state}")

    def metadata_json_enabled(self):
        return bool(self.settings.get("write_metadata_json", False))

    def export_folder(self):
        return self.settings.get("export_dir", "")

    def add_clone(self, source_window):
        x = source_window.x() + source_window.width() + 10
        y = source_window.y()

        window = self._create_window(
            screen_name=source_window.screen_name,
            window_id=self._new_id(),
            locked=False,
            x=x,
            y=y,
        )

        if self.current_payload is not None:
            window.set_payload(self.current_payload)

        window.show()
        window.force_topmost()

    def remove_window(self, window):
        if len(self.windows) <= 1:
            return

        if window.locked:
            self.config_store.remove_window(window.window_id)

        if window in self.windows:
            self.windows.remove(window)

        window.close()

    def set_window_locked(self, window, locked):
        if locked:
            self.config_store.save_window(
                {
                    "id": window.window_id,
                    "screen": window.screen_name,
                    "x": window.x(),
                    "y": window.y(),
                    "locked": True,
                }
            )
        else:
            self.config_store.remove_window(window.window_id)

        window.sync_lock_button()

    def exit_app(self):
        self.app.quit()

    def _save_settings(self):
        self.config_store.save_settings(self.settings)
        self.exporter.configure(
            export_dir=self.settings["export_dir"],
            write_metadata_json=self.settings["write_metadata_json"],
        )

    def _broadcast_save_status(self, ok, message):
        for window in list(self.windows):
            window.set_save_status(ok=ok, message=message)

    def _create_window(self, screen_name, window_id, locked, x, y):
        window = OverlayWindow(
            manager=self,
            window_id=window_id,
            screen_name=screen_name,
            locked=locked,
            initial_x=x,
            initial_y=y,
        )
        self.windows.append(window)
        return window

    def _find_screen(self, screen_name):
        for screen in self.app.screens():
            if screen.name() == screen_name:
                return screen
        return None

    def _new_id(self):
        return uuid.uuid4().hex
