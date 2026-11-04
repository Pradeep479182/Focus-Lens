"""Shared conversion from OpenCV frames to MediaPipe SRGB images."""

from __future__ import annotations

from typing import Any


def create_mediapipe_image(camera_frame: object) -> Any:
    """Convert a CameraFrame's BGR image into the MediaPipe image format."""
    import cv2
    import mediapipe as mp

    bgr_frame = camera_frame.data  # type: ignore[attr-defined]
    rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
