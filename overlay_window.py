from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QWidget, QLabel, QMenu, QHBoxLayout


class OverlayWindow(QWidget):
    NORMAL_COLOR = "white"
    FLASH_COLOR = "limegreen"

    def __init__(
        self,
        manager,
        window_id,
        screen_name,
        locked=False,
        initial_x=None,
        initial_y=None,
    ):
        super().__init__()

        self.manager = manager
        self.window_id = window_id
        self.screen_name = screen_name
        self.locked = locked

        self._drag_start_global = None
        self._drag_start_pos = None

        # CRITICAL: never steal focus
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.label = QLabel("0 bytes")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.label.setStyleSheet(
            f"""
            color: {self.NORMAL_COLOR};
            font-size: 13px;
            font-family: "Segoe UI", "DejaVu Sans", sans-serif;
            """
        )

        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet(
            """
            QWidget#container {
                background-color: rgba(17, 17, 17, 204);
                border: 1px solid rgba(51, 51, 51, 102);
                border-radius: 4px;
            }
            """
        )

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.addWidget(self.label)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.container)

        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.setInterval(2000)
        self.flash_timer.timeout.connect(self._end_flash)

        self.topmost_timer = QTimer(self)
        self.topmost_timer.setInterval(250)
        self.topmost_timer.timeout.connect(self.force_topmost)
        self.topmost_timer.start()

        self.resize(120, 28)

        if initial_x is not None and initial_y is not None:
            self.move(int(initial_x), int(initial_y))

    def set_byte_count(self, byte_count):
        new_text = f"{byte_count} bytes"
        changed = self.label.text() != new_text

        self.label.setText(new_text)
        self._resize_to_fit()

        if changed:
            self.label.setStyleSheet(
                f"""
                color: {self.FLASH_COLOR};
                font-size: 13px;
                font-family: "Segoe UI", "DejaVu Sans", sans-serif;
                """
            )
            self.flash_timer.stop()
            self.flash_timer.start()

    def _end_flash(self):
        self.label.setStyleSheet(
            f"""
            color: {self.NORMAL_COLOR};
            font-size: 13px;
            font-family: "Segoe UI", "DejaVu Sans", sans-serif;
            """
        )

    def _resize_to_fit(self):
        text_width = self.label.fontMetrics().horizontalAdvance(self.label.text())
        self.resize(max(90, text_width + 24), 28)

    def force_topmost(self):
        self.raise_()

    # --- Dragging (only when unlocked) ---
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

    # --- Context menu ---
    def _show_context_menu(self, global_pos: QPoint):
        menu = QMenu(self)

        lock_action = QAction("Unlock" if self.locked else "Lock", self)
        add_clone_action = QAction("Add clone", self)
        remove_action = QAction("Remove", self)
        exit_action = QAction("Exit", self)

        lock_action.triggered.connect(self._toggle_lock)
        add_clone_action.triggered.connect(lambda: self.manager.add_clone(self))
        remove_action.triggered.connect(lambda: self.manager.remove_window(self))
        exit_action.triggered.connect(self.manager.exit_app)

        menu.addAction(lock_action)
        menu.addSeparator()
        menu.addAction(add_clone_action)
        menu.addAction(remove_action)
        menu.addSeparator()
        menu.addAction(exit_action)

        menu.exec(global_pos)

    def _toggle_lock(self):
        self.locked = not self.locked
        self.manager.set_window_locked(self, self.locked)
