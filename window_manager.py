import uuid

from overlay_window import OverlayWindow


class WindowManager:
    OFFSET_X = 220
    OFFSET_Y = 8

    def __init__(self, app, config_store):
        self.app = app
        self.config_store = config_store
        self.windows = []
        self.current_byte_count = 0

    def start(self):
        screens = self.app.screens()
        saved_windows = self.config_store.load_windows(screens)

        # --- Restore locked windows first ---
        for saved in saved_windows:
            screen = self._find_screen(saved["screen"])
            if screen is None:
                continue

            geometry = screen.geometry()
            x, y = self.config_store.clamp_position(
                saved["x"],
                saved["y"],
                geometry,
            )

            window = self._create_window(
                screen_name=saved["screen"],
                window_id=saved["id"],
                locked=True,
                x=x,
                y=y,
            )
            window.show()

        # --- If nothing restored, create ONE window only ---
        if not self.windows:
            primary_screen = self.app.primaryScreen()
            geometry = primary_screen.geometry()

            x = geometry.left() + self.OFFSET_X
            y = geometry.bottom() - 28 - self.OFFSET_Y

            window = self._create_window(
                screen_name=primary_screen.name(),
                window_id=self._new_id(),
                locked=False,
                x=x,
                y=y,
            )
            window.show()

    def update_clipboard_bytes(self, text, byte_count):
        self.current_byte_count = byte_count

        for window in list(self.windows):
            window.set_byte_count(byte_count)

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
        window.set_byte_count(self.current_byte_count)
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

    def exit_app(self):
        self.app.quit()

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
