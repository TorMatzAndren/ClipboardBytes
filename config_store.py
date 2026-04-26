import json
from pathlib import Path


class ConfigStore:
    VERSION = 1
    MIN_VISIBLE_WIDTH = 40

    DEFAULT_SETTINGS = {
        "export_dir": str(Path.home() / "ClipboardBytesExports"),
        "write_metadata_json": False,
    }

    def __init__(self):
        # Dev build uses separate state so it does not inherit bad/stable v1 positions.
        self.config_dir = Path.home() / ".config" / "clipboardbytes-dev"
        self.state_path = self.config_dir / "state.json"

    def load_settings(self):
        data = self._read_state()
        settings = data.get("settings", {})

        result = dict(self.DEFAULT_SETTINGS)

        if isinstance(settings, dict):
            export_dir = settings.get("export_dir")
            write_metadata_json = settings.get("write_metadata_json")

            if isinstance(export_dir, str) and export_dir.strip():
                result["export_dir"] = export_dir

            if isinstance(write_metadata_json, bool):
                result["write_metadata_json"] = write_metadata_json

        return result

    def save_settings(self, settings):
        data = self._read_state()
        clean_settings = dict(self.DEFAULT_SETTINGS)

        export_dir = settings.get("export_dir")
        write_metadata_json = settings.get("write_metadata_json")

        if isinstance(export_dir, str) and export_dir.strip():
            clean_settings["export_dir"] = export_dir

        if isinstance(write_metadata_json, bool):
            clean_settings["write_metadata_json"] = write_metadata_json

        data["version"] = self.VERSION
        data["settings"] = clean_settings
        data.setdefault("windows", [])

        self._write_state(data)

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

        data["version"] = self.VERSION
        data["windows"] = windows
        data.setdefault("settings", dict(self.DEFAULT_SETTINGS))

        self._write_state(data)

    def remove_window(self, window_id):
        data = self._read_state()
        windows = data.get("windows", [])

        windows = [
            item for item in windows
            if isinstance(item, dict) and item.get("id") != window_id
        ]

        data["version"] = self.VERSION
        data["windows"] = windows
        data.setdefault("settings", dict(self.DEFAULT_SETTINGS))

        self._write_state(data)

    def clamp_position(self, x, y, screen_geometry, window_width=150, window_height=82):
        min_left = screen_geometry.left()
        max_left = screen_geometry.right() - self.MIN_VISIBLE_WIDTH

        min_top = screen_geometry.top()
        max_top = screen_geometry.bottom() - max(28, int(window_height))

        clamped_x = max(min_left, min(int(x), max_left))
        clamped_y = max(min_top, min(int(y), max_top))

        return clamped_x, clamped_y

    def _read_state(self):
        try:
            if not self.state_path.exists():
                return self._default_state()

            with self.state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                return self._default_state()

            if data.get("version") != self.VERSION:
                return self._default_state()

            if not isinstance(data.get("windows", []), list):
                data["windows"] = []

            if not isinstance(data.get("settings", {}), dict):
                data["settings"] = dict(self.DEFAULT_SETTINGS)

            return data

        except Exception:
            return self._default_state()

    def _write_state(self, data):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)

            tmp_path = self.state_path.with_suffix(".json.tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

            tmp_path.replace(self.state_path)

        except Exception:
            pass

    def _default_state(self):
        return {
            "version": self.VERSION,
            "settings": dict(self.DEFAULT_SETTINGS),
            "windows": [],
        }
