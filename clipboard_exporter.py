import json
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path


class ClipboardExporter:
    IMAGE_EXTENSIONS = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/gif": ".gif",
        "image/tiff": ".tiff",
    }

    CODE_EXTENSIONS = {
        "python": ".py",
        "bash": ".sh",
        "javascript": ".js",
        "csharp": ".cs",
        "rust": ".rs",
        "markdown": ".md",
        "sql": ".sql",
        "java": ".java",
        "go": ".go",
    }

    def __init__(self, export_dir=None, write_metadata_json=False):
        self.export_dir = Path(export_dir) if export_dir else Path.home() / "ClipboardBytesExports"
        self.write_metadata_json = bool(write_metadata_json)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def configure(self, export_dir=None, write_metadata_json=None):
        if export_dir is not None:
            self.export_dir = Path(export_dir)
            self.export_dir.mkdir(parents=True, exist_ok=True)

        if write_metadata_json is not None:
            self.write_metadata_json = bool(write_metadata_json)

    def open_export_folder(self):
        self.export_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            ["xdg-open", str(self.export_dir)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def export_payload(self, payload, clipboard):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if payload.kind == "text":
            return self._export_text_like(payload, timestamp, "clipboard-text", ".txt")

        if payload.kind == "mixed":
            return self._export_text_like(payload, timestamp, "clipboard-mixed", ".txt")

        if payload.kind == "json":
            return self._export_text_like(payload, timestamp, "clipboard-json", ".json")

        if payload.kind == "html":
            return self._export_text_like(payload, timestamp, "clipboard-html", ".html")

        if payload.kind == "css":
            return self._export_text_like(payload, timestamp, "clipboard-css", ".css")

        if payload.kind in self.CODE_EXTENSIONS:
            return self._export_text_like(
                payload,
                timestamp,
                f"clipboard-{payload.kind}",
                self.CODE_EXTENSIONS[payload.kind],
            )

        if payload.kind == "image":
            return self._export_image(payload, clipboard, timestamp)

        if payload.kind == "files":
            return self._export_files(payload, timestamp)

        return self._export_metadata(payload, timestamp, prefix="clipboard-unknown")

    def _export_text_like(self, payload, timestamp, prefix, suffix):
        base = self.export_dir / f"{prefix}-{timestamp}"
        path = base.with_suffix(suffix)
        path.write_text(payload.text or "", encoding="utf-8")

        paths = [str(path)]
        self._maybe_write_metadata(base, payload, paths)

        return {
            "ok": True,
            "message": f"{payload.kind} saved",
            "paths": paths,
        }

    def _export_image(self, payload, clipboard, timestamp):
        mime_data = clipboard.mimeData()
        mime_type = payload.mime_type

        if mime_type and mime_type.startswith("image/"):
            raw = mime_data.data(mime_type)
            if raw is not None and not raw.isEmpty():
                suffix = self.IMAGE_EXTENSIONS.get(mime_type, ".img")
                base = self.export_dir / f"clipboard-image-{timestamp}"
                raw_path = base.with_suffix(suffix)

                with raw_path.open("wb") as f:
                    f.write(bytes(raw))

                paths = [str(raw_path)]
                self._maybe_write_metadata(base, payload, paths)

                return {
                    "ok": True,
                    "message": "image saved",
                    "paths": paths,
                }

        image = clipboard.image()

        if image.isNull():
            return {
                "ok": False,
                "message": "image unavailable",
                "paths": [],
            }

        base = self.export_dir / f"clipboard-image-{timestamp}"
        png_path = base.with_suffix(".png")

        saved = image.save(str(png_path), "PNG")

        if not saved:
            return {
                "ok": False,
                "message": "image save failed",
                "paths": [],
            }

        paths = [str(png_path)]
        self._maybe_write_metadata(base, payload, paths)

        return {
            "ok": True,
            "message": "image saved",
            "paths": paths,
        }

    def _export_files(self, payload, timestamp):
        base = self.export_dir / f"clipboard-files-{timestamp}"
        list_path = base.with_suffix(".txt")

        list_path.write_text("\n".join(payload.urls) + "\n", encoding="utf-8")

        paths = [str(list_path)]
        self._maybe_write_metadata(base, payload, paths)

        return {
            "ok": True,
            "message": "file list saved",
            "paths": paths,
        }

    def _export_metadata(self, payload, timestamp, prefix="clipboard-metadata"):
        json_path = self.export_dir / f"{prefix}-{timestamp}.json"
        self._write_metadata(json_path, payload)

        return {
            "ok": True,
            "message": "metadata saved",
            "paths": [str(json_path)],
        }

    def _maybe_write_metadata(self, base_path, payload, paths):
        if not self.write_metadata_json:
            return

        json_path = base_path.with_suffix(".metadata.json")
        self._write_metadata(json_path, payload)
        paths.append(str(json_path))

    def _write_metadata(self, path, payload):
        data = asdict(payload)
        data["exported_at"] = datetime.now().isoformat(timespec="seconds")

        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
