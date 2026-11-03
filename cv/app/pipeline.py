"""
FocusLens — CV Pipeline
========================
Orchestrates one complete frame-processing cycle:

    CameraService  ->  FrameProcessor  ->  DevPreview (optional)

The pipeline owns the main capture loop and is the only place that
knows how all services connect together.

Tauri Integration (Day 24)
---------------------------
In integrated mode the pipeline receives downsized JPEG frames over the
local Tauri subprocess stdin and writes newline-delimited JSON activity
signals to stdout. Only derived detection metadata leaves the CV process;
frames are not stored or sent over a network.

Headless mode is enabled by setting ``SHOW_DEV_PREVIEW = False`` in
cv/config/settings.py, or by instantiating ``CVPipeline(headless=True)``.

Day 05 scope
------------
MediaPipe Face Landmarker is now integrated in FrameProcessor.
Headless mode (``SHOW_DEV_PREVIEW = False``) runs the capture loop
without displaying anything — useful for background/integrated use.
"""

from __future__ import annotations

import base64
import binascii
import json
import sys
import time
import datetime

import cv2
import numpy as np

from typing import Any, Dict, Optional, TYPE_CHECKING
from config import SHOW_DEV_PREVIEW, TARGET_FPS
from services.camera_service import CameraFrame, CameraService, CameraError
from services.frame_processor import FrameProcessor
from utils.logger import get_logger

if TYPE_CHECKING:
    from app.dev_preview import DevPreview

log = get_logger(__name__)

# Minimum seconds to wait between frames so we don't spin at 100 % CPU.
_MIN_FRAME_INTERVAL: float = 1.0 / TARGET_FPS if TARGET_FPS > 0 else 0.0


def _emit_signal(signal: Dict[str, Any]) -> None:
    """
    Write one ActivitySignal as newline-delimited JSON to stdout.

    The Tauri sidecar reads stdout line-by-line and converts each line
    to a ``activity-signal`` Tauri event.

    Privacy guarantee: only detection metadata keys are included.
    Raw frame data must never be present in the signal dict.
    """
    safe: Dict[str, Any] = {
        "person_presence": signal.get("person_presence", "UNKNOWN"),
        "screen_facing": signal.get("screen_facing", "UNKNOWN"),
        "posture": signal.get("posture", "UNKNOWN"),
        "confidence": signal.get("confidence", 0.0),
        "timestamp": signal.get("timestamp", time.time()),
        "posture_reminder": bool(signal.get("posture_reminder", False)),
        "occurred_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try:
        line = json.dumps(safe, separators=(",", ":"))
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except (TypeError, ValueError, OSError) as exc:
        log.error("Failed to emit signal to stdout: %s", exc)


def _emit_cv_status(status: str, error_message: Optional[str] = None) -> None:
    """
    Write a ``cv-response`` status line to stdout.

    ``status`` is one of ``'completed'``, ``'unavailable'``, or ``'failed'``.
    This allows the Tauri sidecar to emit a ``cv-response`` event so the
    frontend's ``ActivitySessionMonitor`` can update to ``'unavailable'``
    when the camera is not accessible without treating that as an away event.
    """
    payload: Dict[str, Any] = {
        "__type": "cv_status",
        "status": status,
    }
    if error_message:
        payload["error"] = error_message
    try:
        line = json.dumps(payload, separators=(",", ":"))
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except (TypeError, ValueError, OSError) as exc:
        log.error("Failed to emit cv_status to stdout: %s", exc)


class CVPipeline:
    """
    Runs the FocusLens local computer-vision pipeline.

    The pipeline is intentionally kept simple:

    1. Open the camera.
    2. Loop:
       a. Read a frame.
       b. Process the frame (``FrameProcessor``).
       c. Show the dev preview (if enabled).
       d. Sleep just long enough to approach the target FPS.
    3. On exit (user quit, error, or external stop signal):
       * Release the camera.
       * Close the preview window.

    Usage::

        pipeline = CVPipeline()
        pipeline.run()   # blocks until the user quits

    Call ``pipeline.stop()`` from another thread to request a clean stop.

    Tauri Integration
    -----------------
    Pass ``headless=True`` (or set ``SHOW_DEV_PREVIEW = False``) to run
    without an OpenCV preview window.  In headless mode every state
    change emits a newline-delimited JSON line to stdout so the Tauri
    sidecar can forward it to the frontend as an ``activity-signal`` event.
    """

    def __init__(self, headless: Optional[bool] = None) -> None:
        self._camera = CameraService()
        self._processor = FrameProcessor()
        self._running = False
        # headless=True → no preview window; emit JSON signals to stdout
        # headless=None → respect SHOW_DEV_PREVIEW from config
        if headless is None:
            self._headless = not SHOW_DEV_PREVIEW
        else:
            self._headless = headless

        # Track application state changes across frames
        from services.activity_signal_aggregator import ActivitySignalAggregator
        self._aggregator = ActivitySignalAggregator()

        # DevPreview is imported lazily so the module can be used even
        # if an OpenCV GUI is not available (e.g. headless CI).
        self._preview: Optional['DevPreview'] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Start the capture loop.

        Blocks until:
            * The user presses Q in the preview window.
            * The preview window is closed.
            * ``stop()`` is called from another thread.
            * A non-recoverable camera error occurs.
        """
        log.info("=" * 55)
        log.info("FocusLens — CV Pipeline starting (Day 24)")
        log.info("Privacy: all processing is LOCAL — no data leaves this machine.")
        log.info("Headless mode: %s", self._headless)
        log.info("=" * 55)

        try:
            self._open_camera()
            self._setup_preview()
            self._running = True
            self._capture_loop()
        except CameraError as exc:
            log.error("Camera error: %s", exc)
            if self._headless:
                _emit_cv_status("unavailable", str(exc))
        except KeyboardInterrupt:
            log.info("KeyboardInterrupt received — stopping.")
        finally:
            self._teardown()

    def run_from_stdin(self) -> None:
        """Process newline-delimited JPEG frames supplied by the Tauri host."""
        self._running = True
        log.info("CV pipeline started in host-camera mode.")
        try:
            for line in sys.stdin:
                if not self._running:
                    break
                try:
                    message = json.loads(line)
                    frame_index = message["frame_index"]
                    width = message["width"]
                    height = message["height"]
                    encoded = message["jpeg_base64"]
                    if (
                        isinstance(frame_index, bool)
                        or not isinstance(frame_index, int)
                        or frame_index < 0
                        or isinstance(width, bool)
                        or not isinstance(width, int)
                        or isinstance(height, bool)
                        or not isinstance(height, int)
                        or not 1 <= width <= 1280
                        or not 1 <= height <= 720
                        or not isinstance(encoded, str)
                        or not encoded
                        or len(encoded) > 512 * 1024
                    ):
                        raise ValueError("Invalid frame metadata or payload size.")
                    image_bytes = base64.b64decode(encoded, validate=True)
                    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if image is None or image.shape[1] != width or image.shape[0] != height:
                        raise ValueError("JPEG payload dimensions do not match frame metadata.")
                except (
                    KeyError,
                    TypeError,
                    ValueError,
                    binascii.Error,
                    json.JSONDecodeError,
                    cv2.error,
                ) as exc:
                    log.warning("Ignoring invalid host camera frame: %s", exc)
                    continue

                self._process_frame(
                    CameraFrame(
                        data=image,
                        frame_index=frame_index,
                        width=width,
                        height=height,
                    )
                )
        except Exception as exc:
            log.exception("Host camera CV pipeline failed.")
            _emit_cv_status("failed", str(exc))
        finally:
            self._teardown()

    def stop(self) -> None:
        """
        Request the pipeline to stop after the current frame.

        Thread-safe: the capture loop checks ``self._running`` each iteration.
        """
        log.info("Stop requested.")
        self._running = False

    @property
    def aggregator(self) -> ActivitySignalAggregator:
        """Access the underlying ActivitySignalAggregator."""
        return self._aggregator

    @property
    def current_posture(self) -> str:
        """Return the current stable application posture state."""
        return self._aggregator.current_posture

    def on_activity_signal(self, callback) -> None:
        """
        Subscribe a callback function to receive application activity signals.
        Invoked whenever person presence, screen facing, or posture state changes.
        """
        self._aggregator.add_listener(callback)

    def get_application_state(self) -> dict:
        """Return the current snapshot of application states."""
        return self._aggregator.get_current_state()

    # ------------------------------------------------------------------
    # Private — setup & teardown
    # ------------------------------------------------------------------

    def _open_camera(self) -> None:
        """Open the webcam; propagates ``CameraError`` if it fails."""
        self._camera.open()

    def _setup_preview(self) -> None:
        """Create the dev-preview window if previewing is enabled."""
        if not self._headless and SHOW_DEV_PREVIEW:
            from app.dev_preview import DevPreview
            self._preview = DevPreview()

    def _teardown(self) -> None:
        """Release all resources regardless of how the loop exited."""
        self._running = False
        self._camera.release()
        # Release MediaPipe model resources held by the processor.
        self._processor.close()
        if self._preview is not None:
            self._preview.close()
            self._preview = None
        log.info("CV pipeline stopped cleanly.")

    # ------------------------------------------------------------------
    # Private — capture loop
    # ------------------------------------------------------------------

    def _capture_loop(self) -> None:
        """
        The inner frame-capture loop.

        Each iteration:
            1. Record the start time.
            2. Read one frame from the camera.
            3. Process the frame.
            4. Update the dev preview.
            5. Sleep if we finished faster than the target FPS.
        """
        log.info("Capture loop started. Target FPS: %d.", TARGET_FPS)

        while self._running:
            iter_start = time.perf_counter()

            # --- Capture ---
            try:
                camera_frame = self._camera.read_frame()
            except CameraError as exc:
                log.error("Frame read failed: %s", exc)
                break

            frame_result = self._process_frame(camera_frame)

            # --- Preview ---
            if self._preview is not None:
                self._preview.show(frame_result)
                if self._preview.quit_requested():
                    log.info("Preview quit signal received.")
                    break

            # --- Frame-rate throttle ---
            elapsed = time.perf_counter() - iter_start
            sleep_for = _MIN_FRAME_INTERVAL - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    def _process_frame(self, camera_frame: CameraFrame) -> Any:
        frame_result = self._processor.process(camera_frame)
        signal = self._aggregator.update(frame_result)
        if signal and self._headless:
            _emit_signal(signal)
        return frame_result
