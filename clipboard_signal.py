import hashlib
import time
import traceback
from dataclasses import replace

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from clipboard_payload import ClipboardPayloadReader
from clipboard_diagnostics import (
    ClipboardDiagnostics,
    x11_clipboard_ownership,
)


class ClipboardSignal(QObject):
    observation_ready = pyqtSignal(object)
    payload_changed = pyqtSignal(object)

    def __init__(self, app, diagnostics=None):
        super().__init__()
        self._clipboard = app.clipboard()
        self._reader = ClipboardPayloadReader()
        self._diagnostics = diagnostics or ClipboardDiagnostics()
        self._last_callback_monotonic_ns = None
        self._previous_observation = None
        self._previous_ownership_before = None

        self._last_presentation_signature = None

        self._presentation_timer = QTimer(self)
        self._presentation_timer.setSingleShot(True)
        self._presentation_timer.setInterval(120)
        self._presentation_timer.timeout.connect(
            self._publish_pending_presentation
        )
        self._pending_presentation = None

        self._clipboard.dataChanged.connect(
            self._on_clipboard_changed
        )

    def _on_clipboard_changed(self):
        callback_ns = time.monotonic_ns()
        sequence = self._diagnostics.next_sequence()
        callback_delta_ns = (
            callback_ns - self._last_callback_monotonic_ns
            if self._last_callback_monotonic_ns is not None
            else None
        )
        self._last_callback_monotonic_ns = callback_ns
        ownership_before = x11_clipboard_ownership()
        acquisition_started_ns = time.monotonic_ns()
        self._diagnostics.record(
            "clipboard_callback",
            sequence=sequence,
            callback_monotonic_ns=callback_ns,
            callback_delta_ns=callback_delta_ns,
            x11_ownership_before=(
                ownership_before.to_dict() if ownership_before else None
            ),
        )
        observation = None
        acquisition_error = None
        try:
            observation = self._reader.read_observation(
                self._clipboard
            )
            if sequence is not None:
                observation = replace(
                    observation,
                    diagnostic_sequence=sequence,
                )
        except Exception:
            acquisition_error = "exception"
            print(
                "ClipboardBytes observation acquisition failed:",
                flush=True,
            )
            traceback.print_exc()
        acquisition_finished_ns = time.monotonic_ns()
        ownership_after = x11_clipboard_ownership()

        if self._diagnostics.enabled:
            payload = (
                observation.payload
                if observation is not None
                else None
            )
            content = (
                observation.content_bytes
                if observation is not None
                else None
            )
            mime_formats = (
                payload.raw_formats if payload is not None else None
            )
            if mime_formats is None:
                try:
                    mime_formats = list(self._clipboard.mimeData().formats())
                except Exception:
                    mime_formats = None
            self._diagnostics.record(
                "clipboard_acquisition_complete",
                sequence=sequence,
                mime_formats=mime_formats,
                payload_kind=payload.kind if payload is not None else None,
                payload_sha256=(
                    hashlib.sha256(content).hexdigest()
                    if content is not None
                    else None
                ),
                acquisition_ok=observation is not None,
                acquisition_error=acquisition_error,
                acquisition_duration_ns=(
                    acquisition_finished_ns - acquisition_started_ns
                ),
                x11_ownership_before=(
                    ownership_before.to_dict()
                    if ownership_before
                    else None
                ),
                x11_ownership_after=(
                    ownership_after.to_dict()
                    if ownership_after
                    else None
                ),
            )

        if observation is None:
            self._previous_observation = None
            self._previous_ownership_before = None
            return

        persistence_handoff = self._is_xfce_persistence_handoff(
            self._previous_observation,
            self._previous_ownership_before,
            observation,
            ownership_before,
            ownership_after,
        )
        if persistence_handoff:
            self._diagnostics.record(
                "observation_suppressed_persistence_handoff",
                sequence=sequence,
                payload_kind=observation.payload.kind,
                payload_sha256=hashlib.sha256(
                    observation.content_bytes
                ).hexdigest(),
                owner_window=(
                    ownership_after.clipboard_owner_window
                    if ownership_after
                    else None
                ),
                manager_window=(
                    ownership_after.clipboard_manager_window
                    if ownership_after
                    else None
                ),
            )
        else:
            self._emit_observation(observation)

        self._previous_observation = observation
        self._previous_ownership_before = ownership_before
        self._pending_presentation = observation
        self._presentation_timer.start()

    @staticmethod
    def _is_xfce_persistence_handoff(
        previous_observation,
        previous_ownership_before,
        observation,
        ownership_before,
        ownership_after,
    ):
        """Recognize a stable, byte-identical xfsettingsd takeover."""
        if (
            previous_observation is None
            or previous_observation.content_bytes is None
            or observation.content_bytes is None
            or previous_observation.content_bytes != observation.content_bytes
            or previous_observation.payload.kind != observation.payload.kind
            or previous_observation.payload.mime_type
            != observation.payload.mime_type
            or previous_ownership_before is None
            or ownership_before is None
            or ownership_after is None
        ):
            return False

        if (
            ownership_before != ownership_after
            or not ownership_after.is_xfce_persistence_owner
        ):
            return False

        manager_window = ownership_after.clipboard_manager_window
        manager_pid = ownership_after.clipboard_manager_pid
        return bool(
            manager_window
            and manager_pid
            and previous_ownership_before.clipboard_owner_window
            and previous_ownership_before.clipboard_owner_pid
            and previous_ownership_before.clipboard_owner_window
            != manager_window
            and previous_ownership_before.clipboard_manager_window
            == manager_window
            and previous_ownership_before.clipboard_manager_pid
            == manager_pid
            and previous_ownership_before.clipboard_owner_pid != manager_pid
        )

    def refresh(self):
        """
        Inspect current clipboard state for presentation.

        This is used at application startup and does not create a
        provenance observation.
        """
        observation = self._reader.read_observation(
            self._clipboard
        )
        self._publish_presentation(observation)

    def _refresh_observed_change(self):
        """Compatibility helper for callers that explicitly request capture."""
        ownership_before = x11_clipboard_ownership()
        try:
            observation = self._reader.read_observation(
                self._clipboard
            )
        except Exception:
            print(
                "ClipboardBytes observation acquisition failed:",
                flush=True,
            )
            traceback.print_exc()
            return

        ownership_after = x11_clipboard_ownership()
        if not self._is_xfce_persistence_handoff(
            self._previous_observation,
            self._previous_ownership_before,
            observation,
            ownership_before,
            ownership_after,
        ):
            self._emit_observation(observation)
        self._previous_observation = observation
        self._previous_ownership_before = ownership_before
        self._pending_presentation = observation
        self._publish_pending_presentation()

    def _emit_observation(self, observation):
        try:
            self.observation_ready.emit(observation)
        except Exception:
            print(
                "ClipboardBytes observation consumer failed:",
                flush=True,
            )
            traceback.print_exc()

    def _publish_pending_presentation(self):
        observation = self._pending_presentation
        self._pending_presentation = None
        if observation is None:
            return

        try:
            self._publish_presentation(observation)
        except Exception:
            print(
                "ClipboardBytes presentation publication failed:",
                flush=True,
            )
            traceback.print_exc()

    def _publish_presentation(self, observation):
        payload = observation.payload

        signature = (
            payload.kind,
            payload.size_bytes,
            payload.mime_type,
            payload.subtype,
            self._content_digest(observation.content_bytes),
        )

        if signature == self._last_presentation_signature:
            return

        self._last_presentation_signature = signature
        self.payload_changed.emit(payload)

    @staticmethod
    def _content_digest(content):
        if content is None:
            return None

        return hashlib.sha256(content).digest()
