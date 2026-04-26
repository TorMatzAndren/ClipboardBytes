from datetime import datetime

from PyQt6.QtCore import Qt, QPoint, QTimer, QEvent
from PyQt6.QtWidgets import QWidget, QLabel, QMenu, QVBoxLayout, QHBoxLayout, QPushButton, QToolTip


class OverlayWindow(QWidget):
    FIXED_WIDTH = 168
    FIXED_HEIGHT = 72

    TYPE_COLORS = {
        "text": (22, 180, 75),
        "mixed": (190, 190, 80),
        "json": (35, 210, 135),
        "html": (35, 175, 175),
        "css": (35, 155, 210),
        "markdown": (120, 200, 120),
        "sql": (120, 180, 255),
        "python": (80, 190, 255),
        "csharp": (160, 110, 230),
        "java": (230, 120, 80),
        "go": (70, 210, 230),
        "rust": (210, 130, 70),
        "javascript": (230, 210, 70),
        "bash": (130, 220, 130),
        "image": (95, 90, 230),
        "audio": (230, 135, 30),
        "files": (230, 205, 40),
        "unknown": (180, 70, 70),
    }

    def __init__(self, manager, window_id, screen_name, locked=False, initial_x=None, initial_y=None):
        super().__init__()

        self.manager = manager
        self.window_id = window_id
        self.screen_name = screen_name
        self.locked = locked

        self._drag_start_global = None
        self._drag_start_pos = None
        self._current_kind = "unknown"
        self._copied_at = None
        self._last_payload = None
        self._last_tooltip = "ClipboardBytes"

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(self.FIXED_WIDTH, self.FIXED_HEIGHT)

        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setMouseTracking(True)
        self.container.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)

        self.line1 = self._make_label("UNKNOWN · now", "mainLabel")
        self.line2 = self._make_label("size unavailable", "mainLabel")
        self.line3 = self._make_label("", "detailLabel")

        self.open_button = self._make_button("O")
        self.save_button = self._make_button("S")
        self.clone_button = self._make_button("+")
        self.lock_button = self._make_button("L")

        self.open_button.clicked.connect(self.manager.open_export_folder)
        self.save_button.clicked.connect(self.manager.export_current_payload)
        self.clone_button.clicked.connect(lambda: self.manager.add_clone(self))
        self.lock_button.clicked.connect(self._toggle_lock)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        row.addWidget(self.open_button)
        row.addWidget(self.save_button)
        row.addWidget(self.clone_button)
        row.addWidget(self.lock_button)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(0)
        layout.addWidget(self.line1)
        layout.addWidget(self.line2)
        layout.addWidget(self.line3)
        layout.addLayout(row)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.container)

        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.setInterval(750)
        self.flash_timer.timeout.connect(self._end_flash)

        self.save_status_timer = QTimer(self)
        self.save_status_timer.setSingleShot(True)
        self.save_status_timer.setInterval(1800)
        self.save_status_timer.timeout.connect(self._clear_save_status)

        self.age_timer = QTimer(self)
        self.age_timer.setInterval(1000)
        self.age_timer.timeout.connect(self._refresh_label)
        self.age_timer.start()

        self.topmost_timer = QTimer(self)
        self.topmost_timer.setInterval(250)
        self.topmost_timer.timeout.connect(self.force_topmost)
        self.topmost_timer.start()

        self.sync_lock_button()
        self._apply_style("unknown", flash=False)
        self._apply_tooltip("ClipboardBytes\nNo clipboard payload inspected yet.")

        if initial_x is not None and initial_y is not None:
            self.move(int(initial_x), int(initial_y))

    def _make_label(self, text, object_name):
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        label.setWordWrap(False)
        label.setMouseTracking(True)
        label.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        return label

    def _make_button(self, text):
        button = QPushButton(text)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(12)
        button.setMouseTracking(True)
        button.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        button.setStyleSheet(
            """
            QPushButton {
                color: white;
                background-color: rgba(0, 0, 0, 160);
                border: 1px solid rgba(255, 255, 255, 125);
                border-radius: 2px;
                font-size: 8px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                color: white;
                background-color: rgba(255, 255, 255, 55);
            }
            """
        )
        return button

    def set_payload(self, payload):
        old_text = self.line1.text() + self.line2.text() + self.line3.text()

        self._last_payload = payload
        self._current_kind = payload.kind
        self._copied_at = self._parse_copied_at(payload.copied_at)

        self._refresh_label()

        new_text = self.line1.text() + self.line2.text() + self.line3.text()

        if new_text != old_text:
            self._apply_style(payload.kind, flash=True)
            self.flash_timer.stop()
            self.flash_timer.start()
        else:
            self._apply_style(payload.kind, flash=False)

    def set_save_status(self, ok, message):
        prefix = "ok" if ok else "err"
        self.line3.setText(self._compact(f"{prefix}: {message}", 28))

        self._apply_style(self._current_kind, flash=False, save_state="ok" if ok else "error")
        self.save_status_timer.stop()
        self.save_status_timer.start()

    def sync_lock_button(self):
        self.lock_button.setText("U" if self.locked else "L")

    def force_topmost(self):
        self.raise_()

    def _clear_save_status(self):
        self._refresh_label()
        self._apply_style(self._current_kind, flash=False)

    def _refresh_label(self):
        if self._last_payload is None:
            return

        payload = self._last_payload
        age = self._age_text()

        self.line1.setText(self._compact(f"{payload.kind.upper()} · {age}", 24))
        self.line2.setText(self._compact(payload.size_label, 26))

        if payload.subtype:
            self.line3.setText(self._compact(self._compact_subtype(payload.subtype), 28))
        else:
            self.line3.setText("")

        self._apply_tooltip(self._build_tooltip(payload))

    def _apply_tooltip(self, text):
        self._last_tooltip = text

        for widget in (
            self,
            self.container,
            self.line1,
            self.line2,
            self.line3,
            self.open_button,
            self.save_button,
            self.clone_button,
            self.lock_button,
        ):
            widget.setToolTip(text)

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            if self._last_tooltip:
                QToolTip.showText(event.globalPos(), self._last_tooltip, self)
                return True

        return super().event(event)

    def _compact_subtype(self, subtype):
        subtype = subtype.replace(" · classifier fallback", "")
        subtype = subtype.replace("UTF-8 · ", "")
        subtype = subtype.replace("application/", "")
        subtype = subtype.replace("text/", "")
        subtype = subtype.replace("image/", "")
        subtype = subtype.replace(" · ", " ")

        if "contains " in subtype:
            subtype = subtype.replace("contains ", "+ ")

        return subtype

    def _compact(self, text, max_chars):
        if text is None:
            return ""

        if len(text) <= max_chars:
            return text

        return text[: max_chars - 1] + "…"

    def _age_text(self):
        if self._copied_at is None:
            return "now"

        seconds = max(0, int((datetime.now() - self._copied_at).total_seconds()))

        if seconds < 2:
            return "now"
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            return f"{seconds // 60}m"
        return f"{seconds // 3600}h"

    def _parse_copied_at(self, copied_at):
        try:
            return datetime.fromisoformat(copied_at)
        except Exception:
            return datetime.now()

    def _build_tooltip(self, payload):
        lines = [
            f"Type: {payload.kind}",
            f"Size: {payload.size_label}",
        ]

        if payload.mime_type:
            lines.append(f"MIME: {payload.mime_type}")

        if payload.subtype:
            lines.append(f"Detail: {payload.subtype}")

        if payload.copied_at:
            lines.append(f"Copied: {payload.copied_at}")

        if payload.raw_formats:
            lines.append("")
            lines.append("Clipboard formats:")
            for fmt in payload.raw_formats[:12]:
                lines.append(f"- {fmt}")

        if len(payload.raw_formats) > 12:
            lines.append(f"- ... {len(payload.raw_formats) - 12} more")

        return "\n".join(lines)

    def _apply_style(self, kind, flash=False, save_state=None):
        r, g, b = self.TYPE_COLORS.get(kind, self.TYPE_COLORS["unknown"])

        if flash:
            background = f"rgba({r}, {g}, {b}, 235)"
            border = f"rgba({r}, {g}, {b}, 255)"
            border_width = 4
        else:
            background = "rgba(0, 0, 0, 218)"
            border = f"rgba({r}, {g}, {b}, 235)"
            border_width = 3

        if save_state == "ok":
            border = "rgba(70, 255, 110, 255)"
            border_width = 4
        elif save_state == "error":
            border = "rgba(255, 70, 70, 255)"
            border_width = 4

        self.container.setStyleSheet(
            f"""
            QWidget#container {{
                background-color: {background};
                border: {border_width}px solid {border};
                border-radius: 4px;
            }}
            QLabel#mainLabel {{
                color: white;
                background-color: transparent;
                font-size: 9px;
                font-family: "Segoe UI", "DejaVu Sans", sans-serif;
                font-weight: bold;
            }}
            QLabel#detailLabel {{
                color: rgba(255, 255, 255, 215);
                background-color: transparent;
                font-size: 8px;
                font-family: "Segoe UI", "DejaVu Sans", sans-serif;
                font-weight: bold;
            }}
            """
        )

    def _end_flash(self):
        self._apply_style(self._current_kind, flash=False)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            return

        if event.button() == Qt.MouseButton.LeftButton and not self.locked:
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_pos = self.pos()

    def mouseMoveEvent(self, event):
        if self.locked:
            return

        if self._drag_start_global is None or self._drag_start_pos is None:
            return

        delta = event.globalPosition().toPoint() - self._drag_start_global
        self.move(self._drag_start_pos + delta)

    def mouseReleaseEvent(self, event):
        self._drag_start_global = None
        self._drag_start_pos = None

    def _show_context_menu(self, global_pos: QPoint):
        menu = QMenu(self)

        metadata_text = "Metadata JSON: On" if self.manager.metadata_json_enabled() else "Metadata JSON: Off"

        menu.addAction("Unlock" if self.locked else "Lock", self._toggle_lock)
        menu.addSeparator()
        menu.addAction("Open export folder", self.manager.open_export_folder)
        menu.addAction("Save clipboard", self.manager.export_current_payload)
        menu.addSeparator()
        menu.addAction("Choose export folder", lambda: self.manager.choose_export_folder(self))
        menu.addAction(metadata_text, self.manager.toggle_metadata_json)
        menu.addSeparator()
        menu.addAction("Add clone", lambda: self.manager.add_clone(self))
        menu.addAction("Remove", lambda: self.manager.remove_window(self))
        menu.addSeparator()
        menu.addAction("Exit", self.manager.exit_app)

        menu.exec(global_pos)

    def _toggle_lock(self):
        self.locked = not self.locked
        self.manager.set_window_locked(self, self.locked)
