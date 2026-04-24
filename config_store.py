import json
from pathlib import Path


class ConfigStore:
    VERSION = 1
    MIN_VISIBLE_WIDTH = 40
    ASSUMED_HEIGHT = 28
    ASSUMED_MIN_WIDTH = 90

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "clipboardbytes"
        self.state_path = self.config_dir / "state.json"

    def load_windows(self, screens):
        data = self._read_state()
        windows = data.get("windows", [])

        valid_screen_names = {screen.name() for screen in screens}
        result = []

        for item in windows:
            if not isinstance(item, dict):
                continue

            window_id = item.get("id")
            screen = item.get("screen")
            x = item.get("x")
            y = item.get("y")
            locked = item.get("locked")

            if not isinstance(window_id, str) or not window_id:
                continue

            if screen not in valid_screen_names:
                continue

            if not isinstance(x, int) and not isinstance(x, float):
                continue

            if not isinstance(y, int) and not isinstance(y, float):
                continue

            if locked is not True:
                continue

            result.append(
                {
                    "id": window_id,
                    "screen": screen,
                    "x": int(x),
                    "y": int(y),
                    "locked": True,
                }
            )

        return result

    def save_window(self, window_state):
        data = self._read_state()
        windows = data.get("windows", [])

        windows = [
            item for item in windows
            if isinstance(item, dict) and item.get("id") != window_state["id"]
        ]

        windows.append(
            {
                "id": window_state["id"],
                "screen": window_state["screen"],
                "x": int(window_state["x"]),
                "y": int(window_state["y"]),
                "locked": True,
            }
        )

        self._write_state(
            {
                "version": self.VERSION,
                "windows": windows,
            }
        )

    def remove_window(self, window_id):
        data = self._read_state()
        windows = data.get("windows", [])

        windows = [
            item for item in windows
            if isinstance(item, dict) and item.get("id") != window_id
        ]

        self._write_state(
            {
                "version": self.VERSION,
                "windows": windows,
            }
        )

    def clamp_position(self, x, y, screen_geometry):
        min_left = (
            screen_geometry.left()
            - self.ASSUMED_MIN_WIDTH
            + self.MIN_VISIBLE_WIDTH
        )
        max_left = screen_geometry.right() - self.MIN_VISIBLE_WIDTH
        min_top = screen_geometry.top()
        max_top = screen_geometry.bottom() - self.ASSUMED_HEIGHT

        clamped_x = max(min_left, min(int(x), max_left))
        clamped_y = max(min_top, min(int(y), max_top))

        return clamped_x, clamped_y

    def _read_state(self):
        try:
            if not self.state_path.exists():
                return {"version": self.VERSION, "windows": []}

            with self.state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                return {"version": self.VERSION, "windows": []}

            if data.get("version") != self.VERSION:
                return {"version": self.VERSION, "windows": []}

            if not isinstance(data.get("windows"), list):
                return {"version": self.VERSION, "windows": []}

            return data

        except Exception:
            return {"version": self.VERSION, "windows": []}

    def _write_state(self, data):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)

            tmp_path = self.state_path.with_suffix(".json.tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")

            tmp_path.replace(self.state_path)

        except Exception:
            pass
