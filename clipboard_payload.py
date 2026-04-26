import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice

from code_detector import CodeDetector


@dataclass(frozen=True)
class ClipboardPayload:
    kind: str
    size_bytes: Optional[int]
    size_label: str
    mime_type: Optional[str] = None
    subtype: Optional[str] = None
    text: Optional[str] = None
    urls: list[str] = field(default_factory=list)
    raw_formats: list[str] = field(default_factory=list)
    copied_at: str = ""


def human_size(size_bytes: Optional[int]) -> str:
    if size_bytes is None:
        return "size unavailable"

    units = ["bytes", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "bytes":
                return f"{int(value)} bytes"
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{size_bytes} bytes"


class ClipboardPayloadReader:
    def __init__(self):
        self.code_detector = CodeDetector()

    def read(self, clipboard) -> ClipboardPayload:
        mime_data = clipboard.mimeData()
        raw_formats = list(mime_data.formats())
        copied_at = datetime.now().isoformat(timespec="seconds")

        image_format = self._first_matching_format(raw_formats, "image/")
        if mime_data.hasImage() or image_format or "application/x-qt-image" in raw_formats:
            return self._read_image(clipboard, mime_data, raw_formats, copied_at)

        if mime_data.hasUrls():
            return self._read_urls(mime_data, raw_formats, copied_at)

        audio_payload = self._try_read_audio(mime_data, raw_formats, copied_at)
        if audio_payload is not None:
            return audio_payload

        if mime_data.hasText():
            return self._read_text(mime_data.text() or "", raw_formats, copied_at)

        return ClipboardPayload(
            kind="unknown",
            size_bytes=None,
            size_label=human_size(None),
            mime_type=raw_formats[0] if raw_formats else None,
            raw_formats=raw_formats,
            copied_at=copied_at,
        )

    def _read_text(self, text, raw_formats, copied_at):
        size_bytes = len(text.encode("utf-8"))

        mixed_subtype = self._detect_mixed_text(text)
        if mixed_subtype:
            return ClipboardPayload(
                kind="mixed",
                size_bytes=size_bytes,
                size_label=human_size(size_bytes),
                mime_type="text/plain",
                subtype=mixed_subtype,
                text=text,
                raw_formats=raw_formats,
                copied_at=copied_at,
            )

        json_subtype = self._detect_json_subtype(text)
        if json_subtype:
            return ClipboardPayload(
                kind="json",
                size_bytes=size_bytes,
                size_label=human_size(size_bytes),
                mime_type="application/json",
                subtype=json_subtype,
                text=text,
                raw_formats=raw_formats,
                copied_at=copied_at,
            )

        code = self.code_detector.detect(text)
        if code:
            return ClipboardPayload(
                kind=code.language,
                size_bytes=size_bytes,
                size_label=human_size(size_bytes),
                mime_type=f"text/x-{code.language}",
                subtype=f"{code.subtype} · {code.confidence}% {code.tier}",
                text=text,
                raw_formats=raw_formats,
                copied_at=copied_at,
            )

        if self._looks_like_html(text):
            return ClipboardPayload(
                kind="html",
                size_bytes=size_bytes,
                size_label=human_size(size_bytes),
                mime_type="text/html",
                subtype="HTML",
                text=text,
                raw_formats=raw_formats,
                copied_at=copied_at,
            )

        if self._looks_like_css(text):
            return ClipboardPayload(
                kind="css",
                size_bytes=size_bytes,
                size_label=human_size(size_bytes),
                mime_type="text/css",
                subtype="CSS",
                text=text,
                raw_formats=raw_formats,
                copied_at=copied_at,
            )

        hints = self.code_detector.scan_hints(text)
        if hints:
            hint_text = ", ".join(f"{name} {confidence}%" for name, confidence in hints)
            subtype = f"UTF-8 · contains {hint_text}"
        else:
            subtype = "UTF-8 · classifier fallback"

        return ClipboardPayload(
            kind="text",
            size_bytes=size_bytes,
            size_label=human_size(size_bytes),
            mime_type="text/plain",
            subtype=subtype,
            text=text,
            raw_formats=raw_formats,
            copied_at=copied_at,
        )

    def _detect_mixed_text(self, text):
        stripped = text.strip()
        if not stripped:
            return None

        try:
            json.loads(stripped)
            return None
        except Exception:
            pass

        header_hits = re.findall(
            r"^={3,}\s*([^=\n]+\.(json|tsx|ts|js|css|py|rs|go|java|cs|sql|md|html))\s*={3,}\s*$",
            text,
            re.MULTILINE,
        )

        path_hits = re.findall(
            r"(^|\s)/(?:opt|home|mnt|var|etc)/[^\s]+?\.(json|tsx|ts|js|css|py|rs|go|java|cs|sql|md|html)\b",
            text,
            re.MULTILINE,
        )

        explicit_file_bundle = len(header_hits) >= 2 or len(path_hits) >= 2

        signals = []
        if explicit_file_bundle:
            signals.append("file-bundle")

        masked = self._mask_quoted_strings(text)

        json_like = bool(
            re.search(r"(^|\n)\s*\{\s*\n\s*\"[^\"]+\"\s*:", text)
            or re.search(r"(^|\n)\s*\[\s*\n\s*\{", text)
        )

        js_like = bool(
            re.search(r"\b(import|export)\s+.*\bfrom\s+['\"]", text)
            or re.search(r"\b(const|let|var)\s+\w+\s*=", text)
            or re.search(r"\bfunction\s+\w+\s*\(", text)
            or re.search(r"\bconsole\.log\s*\(", text)
            or re.search(r"=>", text)
        )

        css_like = bool(
            re.search(r"(^|\n)\s*[.#]?[A-Za-z][\w\-]*(?:\[[^\]]+\])?(?:::?[A-Za-z][\w\-]*)?\s*\{[^{}]+:[^{}]+", masked)
        )

        python_like = bool(re.search(r"^\s*(from|import|def|class)\s+\w+", text, re.MULTILINE))
        markdown_like = bool(
            re.search(r"^\s*#\s+\w+", text, re.MULTILINE)
            and re.search(r"^\s*[-*+]\s+\w+", text, re.MULTILINE)
        )

        prose_like = self._looks_like_explanatory_prose(text)

        if json_like:
            signals.append("json-like")
        if js_like:
            signals.append("js/tsx")
        if css_like:
            signals.append("css")
        if python_like:
            signals.append("python")
        if markdown_like:
            signals.append("markdown")

        unique = []
        for signal in signals:
            if signal not in unique:
                unique.append(signal)

        if explicit_file_bundle and len(unique) >= 2:
            return "mixed · " + ", ".join(unique[:5])

        if prose_like:
            return None

        structural = [s for s in unique if s != "file-bundle"]

        if "markdown" in structural and not explicit_file_bundle:
            return None

        if len(structural) >= 3:
            return "mixed · " + ", ".join(structural[:5])

        return None

    def _looks_like_explanatory_prose(self, text):
        prose_lines = 0

        for line in text.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if stripped.startswith(("#", "//", "--", "-", "*", ">", "```")):
                continue

            if len(stripped) >= 20 and re.search(
                r"\b(this|that|here|example|note|several|clipboard|works|source file|not a|about|following)\b",
                stripped,
                re.IGNORECASE,
            ):
                prose_lines += 1

        return prose_lines >= 2

    def _mask_quoted_strings(self, text):
        def repl(match):
            quote = match.group(0)[0]
            return quote + "STRING" + quote

        return re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", repl, text)

    def _read_image(self, clipboard, mime_data, raw_formats, copied_at):
        mime_type = self._first_matching_format(raw_formats, "image/")

        size_bytes = None
        width = None
        height = None

        if mime_type:
            raw = mime_data.data(mime_type)
            if raw is not None and not raw.isEmpty():
                size_bytes = raw.size()

        if size_bytes is None and "application/x-qt-image" in raw_formats:
            raw = mime_data.data("application/x-qt-image")
            if raw is not None and not raw.isEmpty():
                size_bytes = raw.size()

        image = clipboard.image()
        if not image.isNull():
            width = image.width()
            height = image.height()

            if size_bytes is None:
                encoded_size = self._encoded_png_size(image)
                if encoded_size is not None:
                    size_bytes = encoded_size
                    mime_type = mime_type or "image/png"

        format_label = mime_type or "application/x-qt-image"
        subtype = f"{format_label} · {width}x{height}" if width and height else format_label

        return ClipboardPayload(
            kind="image",
            size_bytes=size_bytes,
            size_label=human_size(size_bytes),
            mime_type=format_label,
            subtype=subtype,
            raw_formats=raw_formats,
            copied_at=copied_at,
        )

    def _encoded_png_size(self, image):
        try:
            data = QByteArray()
            buffer = QBuffer(data)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            ok = image.save(buffer, "PNG")
            buffer.close()
            if ok:
                return data.size()
        except Exception:
            return None
        return None

    def _read_urls(self, mime_data, raw_formats, copied_at):
        urls = mime_data.urls()
        url_strings = [url.toString() for url in urls]

        file_paths = []
        total_size = 0
        all_file_sizes_known = True

        for url in urls:
            if not url.isLocalFile():
                all_file_sizes_known = False
                continue

            path = Path(url.toLocalFile())
            file_paths.append(str(path))

            try:
                if path.is_file():
                    total_size += path.stat().st_size
                else:
                    all_file_sizes_known = False
            except OSError:
                all_file_sizes_known = False

        size_bytes = total_size if file_paths and all_file_sizes_known else None

        return ClipboardPayload(
            kind="files",
            size_bytes=size_bytes,
            size_label=human_size(size_bytes),
            mime_type="text/uri-list",
            subtype=f"{len(urls)} item" if len(urls) == 1 else f"{len(urls)} items",
            urls=url_strings,
            raw_formats=raw_formats,
            copied_at=copied_at,
        )

    def _try_read_audio(self, mime_data, raw_formats, copied_at):
        mime_type = self._first_matching_format(raw_formats, "audio/")
        if not mime_type:
            return None

        raw = mime_data.data(mime_type)
        size_bytes = raw.size() if raw is not None and not raw.isEmpty() else None

        return ClipboardPayload(
            kind="audio",
            size_bytes=size_bytes,
            size_label=human_size(size_bytes),
            mime_type=mime_type,
            subtype=mime_type,
            raw_formats=raw_formats,
            copied_at=copied_at,
        )

    def _detect_json_subtype(self, text):
        stripped = text.strip()
        if not stripped:
            return None

        if not (
            stripped.startswith("{")
            or stripped.startswith("[")
            or stripped.startswith('"')
            or stripped in {"true", "false", "null"}
            or re.fullmatch(r"-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?", stripped)
        ):
            return None

        try:
            value = json.loads(stripped)
        except Exception:
            return None

        if isinstance(value, dict):
            return f"object{{{len(value)}}}"
        if isinstance(value, list):
            return f"array[{len(value)}]"
        if isinstance(value, str):
            return "string"
        if isinstance(value, bool):
            return "boolean"
        if value is None:
            return "null"
        if isinstance(value, int) or isinstance(value, float):
            return "number"

        return "json"

    def _looks_like_html(self, text):
        stripped = text.strip()
        if not stripped:
            return False

        if re.search(r"\bimport\s+React\b|\bexport\s+default\b|\bfrom\s+['\"]react['\"]", stripped):
            return False

        masked = self._mask_quoted_strings(stripped)
        lowered = masked.lower()

        if lowered.startswith("<!doctype html"):
            return True

        if lowered.startswith("<html") and "</html>" in lowered:
            return True

        return bool(
            re.search(
                r"<(div|span|p|a|body|head|script|style|section|article|table|ul|ol|li|pre|code|html|h1)\b[^>]*>.*</\1>",
                masked,
                re.IGNORECASE | re.DOTALL,
            )
            and not re.search(r"\bfunction\s+\w+\s*\(|=>|return\s+<", stripped)
        )

    def _looks_like_css(self, text):
        stripped = text.strip()
        if not stripped:
            return False

        if "<" in self._mask_quoted_strings(stripped) or ">" in self._mask_quoted_strings(stripped):
            return False

        if re.search(r"^\s*(from|import|def|class)\s+\w+", stripped, re.MULTILINE):
            return False

        masked = self._mask_quoted_strings(stripped)

        css_blocks = re.findall(
            r"(^|[\n\r}])\s*([.#]?[a-zA-Z][\w\-]*(?:\[[^\]]+\])?(?:::?[a-zA-Z][\w\-]*)?(?:\s+[.#]?[a-zA-Z][\w\-]*)?|[a-zA-Z][\w\-]*\s*[>+~]\s*[a-zA-Z][\w\-]*)\s*\{([^{}]+)\}",
            masked,
            re.DOTALL,
        )

        if not css_blocks:
            return False

        property_count = 0
        for _, selector, body in css_blocks:
            declarations = re.findall(r"(^|;|\n)\s*[a-zA-Z-]+\s*:\s*(?:'[^']*'|\"[^\"]*\"|[^;{}\n]+)", body)
            property_count += len(declarations)

        return property_count >= 2

    def _first_matching_format(self, formats, prefix):
        for fmt in formats:
            if fmt.startswith(prefix):
                return fmt
        return None
