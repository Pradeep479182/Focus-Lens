"""Tests that both MediaPipe models share one converted frame per cycle."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from models.cv_results import PersonState
from services.face_landmarker import FaceDetectionResult, FaceDetectionState
from services.frame_processor import FrameProcessor
from services.pose_landmarker import PoseDetectionResult, PoseDetectionState


class SharedImageConversionTests(unittest.TestCase):
    def test_available_detectors_share_one_prepared_image(self) -> None:
        with patch("services.frame_processor.FaceLandmarkerService"), patch(
            "services.frame_processor.PoseLandmarkerService"
        ):
            processor = FrameProcessor()

        frame = SimpleNamespace(
            data=np.zeros((48, 64, 3), dtype=np.uint8),
            frame_index=1,
        )
        image = object()
        face = MagicMock(is_available=True)
        face.detect.return_value = FaceDetectionResult(
            available=True,
            state=FaceDetectionState.NOT_DETECTED,
        )
        pose = MagicMock(is_available=True)
        pose.detect.return_value = PoseDetectionResult(
            available=True,
            state=PoseDetectionState.NOT_DETECTED,
        )
        processor._face_landmarker = face
        processor._pose_landmarker = pose

        try:
            with patch(
                "services.frame_processor.create_mediapipe_image",
                return_value=image,
            ) as create_image:
                result = processor.process(frame)

            create_image.assert_called_once_with(frame)
            face.detect.assert_called_once_with(frame, image)
            pose.detect.assert_called_once_with(frame, image)
            self.assertEqual(result.person_state, PersonState.UNKNOWN)
            self.assertEqual(result.posture_state, "UNKNOWN")
        finally:
            processor.close()


if __name__ == "__main__":
    unittest.main()
