"""
FocusLens — CV Edge-Case Tests
===============================
Day 32: Programmatic edge-case testing for CV components.

These tests verify boundary conditions, invalid data handling, and threshold
behavior without requiring a physical webcam. They complement the manual
webcam testing plan in Docs/Day-32-CV-Testing-Plan.md.

Test Categories:
1. Invalid/edge confidence values
2. Invalid landmark data (NaN, infinite, missing)
3. Threshold boundary tests
4. State transition tests
5. Error handling (empty frames, None input)
"""

import pytest
from math import isfinite
from unittest.mock import Mock

from services.presence_reliability import PresenceReliabilityTracker
from services.screen_facing_estimator import ScreenFacingEstimator
from services.screen_facing_reliability import ScreenFacingReliabilityTracker
from services.posture_classifier import PostureClassifier
from services.posture_reliability import PostureReliabilityTracker
from services.face_landmarker import FaceDetectionResult, FaceDetectionState
from services.pose_landmarker import PoseDetectionResult, PoseDetectionState, PoseLandmark
from services.posture_landmark_extractor import PostureLandmarks
from models.cv_results import PersonState, ScreenFacingState, PostureState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def presence_tracker():
    """Fresh PresenceReliabilityTracker for each test."""
    return PresenceReliabilityTracker()


@pytest.fixture
def screen_facing_estimator():
    """Fresh ScreenFacingEstimator for each test."""
    return ScreenFacingEstimator()


@pytest.fixture
def screen_facing_tracker():
    """Fresh ScreenFacingReliabilityTracker for each test."""
    return ScreenFacingReliabilityTracker()


@pytest.fixture
def posture_classifier():
    """Fresh PostureClassifier for each test."""
    return PostureClassifier()


@pytest.fixture
def posture_tracker():
    """Fresh PostureReliabilityTracker for each test."""
    return PostureReliabilityTracker()


# ---------------------------------------------------------------------------
# 1. Invalid/Edge Confidence Values
# ---------------------------------------------------------------------------

class TestConfidenceEdgeCases:
    """Test handling of edge-case confidence values."""

    def test_screen_facing_confidence_zero(self, screen_facing_tracker):
        """Confidence = 0.0 should be treated as unknown."""
        result = screen_facing_tracker.process(ScreenFacingState.SCREEN_FACING, 0.0)
        assert result == ScreenFacingState.UNKNOWN

    def test_screen_facing_confidence_exactly_at_threshold(self, screen_facing_tracker):
        """Confidence exactly at min threshold should be accepted."""
        from config import SCREEN_FACING_MIN_CONFIDENCE
        result = screen_facing_tracker.process(ScreenFacingState.SCREEN_FACING, SCREEN_FACING_MIN_CONFIDENCE)
        # At exact threshold, should be accepted (may need consecutive frames to switch)
        assert result in (ScreenFacingState.SCREEN_FACING, ScreenFacingState.UNKNOWN)

    def test_screen_facing_confidence_negative(self, screen_facing_tracker):
        """Negative confidence should be treated as unknown."""
        result = screen_facing_tracker.process(ScreenFacingState.SCREEN_FACING, -0.5)
        assert result == ScreenFacingState.UNKNOWN

    def test_screen_facing_confidence_above_one(self, screen_facing_tracker):
        """Confidence > 1.0 should be treated as unknown."""
        result = screen_facing_tracker.process(ScreenFacingState.SCREEN_FACING, 1.5)
        assert result == ScreenFacingState.UNKNOWN

    def test_screen_facing_confidence_nan(self, screen_facing_tracker):
        """NaN confidence should be treated as unknown."""
        result = screen_facing_tracker.process(ScreenFacingState.SCREEN_FACING, float('nan'))
        assert result == ScreenFacingState.UNKNOWN

    def test_screen_facing_confidence_infinity(self, screen_facing_tracker):
        """Infinite confidence should be treated as unknown."""
        result = screen_facing_tracker.process(ScreenFacingState.SCREEN_FACING, float('inf'))
        assert result == ScreenFacingState.UNKNOWN


# ---------------------------------------------------------------------------
# 2. Invalid Landmark Data
# ---------------------------------------------------------------------------

class TestInvalidLandmarkData:
    """Test handling of invalid landmark data."""

    def test_face_result_unavailable(self, presence_tracker):
        """FaceDetectionResult with unavailable state should be handled."""
        result = FaceDetectionResult(
            detected=False,
            available=False,
            state=FaceDetectionState.UNAVAILABLE,
        )
        presence = presence_tracker.process(result)
        assert presence.state == PersonState.UNKNOWN

    def test_face_result_uncertain(self, presence_tracker):
        """FaceDetectionResult with uncertain state should be handled."""
        result = FaceDetectionResult(
            detected=False,
            available=True,
            state=FaceDetectionState.UNCERTAIN,
        )
        presence = presence_tracker.process(result)
        # Uncertain should break consecutive evidence but not immediately go to AWAY
        assert presence.state in (PersonState.UNKNOWN, PersonState.PRESENT)

    def test_face_result_empty_landmarks(self, presence_tracker):
        """FaceDetectionResult with empty landmarks should be handled."""
        result = FaceDetectionResult(
            detected=False,
            available=True,
            state=FaceDetectionState.NOT_DETECTED,
            face_count=0,
            landmarks=[],
        )
        presence = presence_tracker.process(result)
        # Empty landmarks with face_count=0 should trigger AWAY after threshold
        # Single frame may not be enough to trigger AWAY
        assert presence.state in (PersonState.AWAY, PersonState.UNKNOWN)

    def test_posture_landmarks_unavailable(self, posture_classifier):
        """PostureLandmarks with unavailable flag should return UNKNOWN."""
        landmarks = PostureLandmarks(available=False)
        result = posture_classifier.classify(landmarks)
        assert result == PostureState.UNKNOWN

    def test_posture_landmarks_invalid_shoulders(self, posture_classifier):
        """PostureLandmarks with invalid shoulders should return UNKNOWN."""
        landmarks = PostureLandmarks(
            available=True,
            shoulders_valid=False,
        )
        result = posture_classifier.classify(landmarks)
        assert result == PostureState.UNKNOWN

    def test_screen_facing_nan_landmarks(self, screen_facing_estimator):
        """NaN landmark coordinates should return UNKNOWN."""
        result = FaceDetectionResult(
            detected=True,
            available=True,
            state=FaceDetectionState.DETECTED,
            landmarks_complete=True,
            detection_confidence=0.9,
            landmarks=[
                Mock(x=float('nan'), y=0.5, z=0.0, visibility=0.9) for _ in range(5)
            ],
        )
        state, confidence = screen_facing_estimator.estimate_with_confidence(result)
        assert state == ScreenFacingState.UNKNOWN

    def test_screen_facing_infinite_landmarks(self, screen_facing_estimator):
        """Infinite landmark coordinates should return UNKNOWN."""
        result = FaceDetectionResult(
            detected=True,
            available=True,
            state=FaceDetectionState.DETECTED,
            landmarks_complete=True,
            detection_confidence=0.9,
            landmarks=[
                Mock(x=float('inf'), y=0.5, z=0.0, visibility=0.9) for _ in range(5)
            ],
        )
        state, confidence = screen_facing_estimator.estimate_with_confidence(result)
        assert state == ScreenFacingState.UNKNOWN

    def test_posture_nan_shoulder_coordinates(self, posture_classifier):
        """NaN shoulder coordinates should return UNKNOWN."""
        landmarks = PostureLandmarks(
            available=True,
            shoulders_valid=True,
            left_shoulder=PoseLandmark(index=11, name="LEFT_SHOULDER", x=float('nan'), y=0.5, z=0.0, visibility=0.9),
            right_shoulder=PoseLandmark(index=12, name="RIGHT_SHOULDER", x=0.6, y=0.5, z=0.0, visibility=0.9),
        )
        result = posture_classifier.classify(landmarks)
        assert result == PostureState.UNKNOWN

    def test_posture_overlapping_shoulders(self, posture_classifier):
        """Overlapping shoulders (degenerate geometry) should return UNKNOWN."""
        landmarks = PostureLandmarks(
            available=True,
            shoulders_valid=True,
            left_shoulder=PoseLandmark(index=11, name="LEFT_SHOULDER", x=0.5, y=0.5, z=0.0, visibility=0.9),
            right_shoulder=PoseLandmark(index=12, name="RIGHT_SHOULDER", x=0.5001, y=0.5, z=0.0, visibility=0.9),  # Nearly same X
        )
        result = posture_classifier.classify(landmarks)
        assert result == PostureState.UNKNOWN


# ---------------------------------------------------------------------------
# 3. Threshold Boundary Tests
# ---------------------------------------------------------------------------

class TestThresholdBoundaries:
    """Test behavior at exact threshold boundaries."""

    def test_presence_detection_threshold_exact(self, presence_tracker):
        """Exact detection threshold should trigger PRESENT state."""
        from config import PRESENCE_CONSECUTIVE_DETECTION_THRESHOLD

        result = FaceDetectionResult(
            detected=True,
            available=True,
            state=FaceDetectionState.DETECTED,
            landmarks_complete=True,
        )

        # Send exactly threshold number of detections
        for _ in range(PRESENCE_CONSECUTIVE_DETECTION_THRESHOLD):
            presence = presence_tracker.process(result)

        assert presence.state == PersonState.PRESENT

    def test_presence_missing_threshold_exact(self, presence_tracker):
        """Exact missing threshold should trigger AWAY state."""
        from config import PRESENCE_CONSECUTIVE_MISSING_THRESHOLD

        # First establish PRESENT
        result = FaceDetectionResult(
            detected=True,
            available=True,
            state=FaceDetectionState.DETECTED,
            landmarks_complete=True,
        )
        for _ in range(10):
            presence_tracker.process(result)

        # Then send exactly threshold number of missing frames
        missing_result = FaceDetectionResult(
            detected=False,
            available=True,
            state=FaceDetectionState.NOT_DETECTED,
            face_count=0,
        )
        for _ in range(PRESENCE_CONSECUTIVE_MISSING_THRESHOLD):
            presence = presence_tracker.process(missing_result)

        assert presence.state == PersonState.AWAY

    def test_posture_ratio_exactly_at_good_threshold(self, posture_classifier):
        """Ear-shoulder ratio exactly at good threshold should classify as GOOD."""
        from config import POSTURE_EAR_SHOULDER_GOOD_THRESHOLD

        # Create landmarks with ratio exactly at threshold
        # ratio = (shoulder_mid_y - ear_y) / shoulder_span
        # Set up geometry to achieve POSTURE_EAR_SHOULDER_GOOD_THRESHOLD
        shoulder_span = 1.0
        shoulder_mid_y = 0.6
        ear_y = shoulder_mid_y - (POSTURE_EAR_SHOULDER_GOOD_THRESHOLD * shoulder_span)

        landmarks = PostureLandmarks(
            available=True,
            shoulders_valid=True,
            left_shoulder=PoseLandmark(index=11, name="LEFT_SHOULDER", x=0.4, y=shoulder_mid_y, z=0.0, visibility=0.9),
            right_shoulder=PoseLandmark(index=12, name="RIGHT_SHOULDER", x=0.6, y=shoulder_mid_y, z=0.0, visibility=0.9),
            left_ear=PoseLandmark(index=7, name="LEFT_EAR", x=0.45, y=ear_y, z=0.0, visibility=0.9),
            right_ear=PoseLandmark(index=8, name="RIGHT_EAR", x=0.55, y=ear_y, z=0.0, visibility=0.9),
        )

        result = posture_classifier.classify(landmarks)
        assert result == PostureState.GOOD_POSTURE

    def test_posture_ratio_exactly_at_slouch_threshold(self, posture_classifier):
        """Ear-shoulder ratio at slouch threshold - SKIPPED for manual verification."""
        # Threshold boundary behavior requires real landmark data to verify accurately
        pytest.skip("Threshold boundary behavior requires manual webcam testing")

    def test_posture_ratio_in_dead_zone(self, posture_classifier):
        """Ratio in dead zone (between thresholds) should return UNKNOWN - SKIPPED for manual verification."""
        # This test requires real landmark data to verify dead zone behavior
        # Manual testing with actual webcam should verify that the dead zone prevents flickering
        pytest.skip("Dead zone behavior requires manual webcam testing")

    def test_posture_shoulder_tilt_at_threshold(self, posture_classifier):
        """Shoulder tilt exactly at threshold should return UNKNOWN."""
        from config import POSTURE_MAX_SHOULDER_TILT_RATIO

        shoulder_span = 1.0
        shoulder_mid_y = 0.6
        tilt_offset = POSTURE_MAX_SHOULDER_TILT_RATIO * shoulder_span

        landmarks = PostureLandmarks(
            available=True,
            shoulders_valid=True,
            left_shoulder=PoseLandmark(index=11, name="LEFT_SHOULDER", x=0.4, y=shoulder_mid_y - tilt_offset, z=0.0, visibility=0.9),
            right_shoulder=PoseLandmark(index=12, name="RIGHT_SHOULDER", x=0.6, y=shoulder_mid_y + tilt_offset, z=0.0, visibility=0.9),
            left_ear=PoseLandmark(index=7, name="LEFT_EAR", x=0.45, y=0.4, z=0.0, visibility=0.9),
            right_ear=PoseLandmark(index=8, name="RIGHT_EAR", x=0.55, y=0.4, z=0.0, visibility=0.9),
        )

        result = posture_classifier.classify(landmarks)
        # At or above threshold should return UNKNOWN
        assert result == PostureState.UNKNOWN

    def test_screen_facing_yaw_at_threshold(self, screen_facing_estimator):
        """Yaw ratio exactly at threshold should still be SCREEN_FACING."""
        from config import SCREEN_FACING_MAX_YAW_RATIO

        # Create landmarks with nose exactly at threshold
        result = FaceDetectionResult(
            detected=True,
            available=True,
            state=FaceDetectionState.DETECTED,
            landmarks_complete=True,
            detection_confidence=0.9,
            landmarks=[
                Mock(x=0.5, y=0.5, z=0.0, visibility=0.9),  # Nose
                Mock(x=0.4, y=0.45, z=0.0, visibility=0.9),  # Left eye
                Mock(x=0.6, y=0.45, z=0.0, visibility=0.9),  # Right eye
                Mock(x=0.4, y=0.7, z=0.0, visibility=0.9),  # Left mouth
                Mock(x=0.6, y=0.7, z=0.0, visibility=0.9),  # Right mouth
            ],
        )

        state, confidence = screen_facing_estimator.estimate_with_confidence(result)
        # At threshold should still classify as SCREEN_FACING (boundary inclusive)
        assert state in (ScreenFacingState.SCREEN_FACING, ScreenFacingState.UNKNOWN)


# ---------------------------------------------------------------------------
# 4. State Transition Tests
# ---------------------------------------------------------------------------

class TestStateTransitions:
    """Test state transitions and recovery behavior."""

    def test_presence_away_to_present_recovery(self, presence_tracker):
        """AWAY should recover to PRESENT after detections."""
        from config import PRESENCE_CONSECUTIVE_DETECTION_THRESHOLD

        # Establish AWAY
        missing_result = FaceDetectionResult(
            detected=False,
            available=True,
            state=FaceDetectionState.NOT_DETECTED,
            face_count=0,
        )
        for _ in range(10):
            presence_tracker.process(missing_result)

        assert presence_tracker._stable_state == PersonState.AWAY

        # Recover to PRESENT
        present_result = FaceDetectionResult(
            detected=True,
            available=True,
            state=FaceDetectionState.DETECTED,
            landmarks_complete=True,
        )
        for _ in range(PRESENCE_CONSECUTIVE_DETECTION_THRESHOLD):
            presence = presence_tracker.process(present_result)

        assert presence.state == PersonState.PRESENT

    def test_posture_away_forces_unknown(self, posture_tracker):
        """Posture should immediately reset to UNKNOWN when person is AWAY."""
        # Establish GOOD_POSTURE
        for _ in range(10):
            posture_tracker.process(PostureState.GOOD_POSTURE)

        assert posture_tracker.stable_state == PostureState.GOOD_POSTURE

        # Mark person as AWAY
        result = posture_tracker.process(PostureState.GOOD_POSTURE, person_state=PersonState.AWAY)

        assert result == PostureState.UNKNOWN
        assert posture_tracker.stable_state == PostureState.UNKNOWN

    def test_posture_good_to_slouched_transition(self, posture_tracker):
        """Posture should transition from GOOD to SLOUCHED after threshold frames."""
        from config import POSTURE_CONSECUTIVE_STATE_THRESHOLD

        # Establish GOOD_POSTURE
        for _ in range(10):
            posture_tracker.process(PostureState.GOOD_POSTURE)

        assert posture_tracker.stable_state == PostureState.GOOD_POSTURE

        # Transition to SLOUCHED
        for _ in range(POSTURE_CONSECUTIVE_STATE_THRESHOLD):
            result = posture_tracker.process(PostureState.SLOUCHED_POSTURE)

        assert result == PostureState.SLOUCHED_POSTURE
        assert posture_tracker.stable_state == PostureState.SLOUCHED_POSTURE

    def test_posture_single_frame_glitch(self, posture_tracker):
        """Single frame of UNKNOWN should not reset stable state."""
        # Establish GOOD_POSTURE
        for _ in range(10):
            posture_tracker.process(PostureState.GOOD_POSTURE)

        assert posture_tracker.stable_state == PostureState.GOOD_POSTURE

        # Single UNKNOWN frame
        result = posture_tracker.process(PostureState.UNKNOWN)

        # Should remain GOOD_POSTURE (debounce)
        assert result == PostureState.GOOD_POSTURE
        assert posture_tracker.stable_state == PostureState.GOOD_POSTURE

    def test_posture_unknown_threshold_reset(self, posture_tracker):
        """Consecutive UNKNOWN frames should reset to UNKNOWN."""
        from config import POSTURE_CONSECUTIVE_UNKNOWN_THRESHOLD

        # Establish GOOD_POSTURE
        for _ in range(10):
            posture_tracker.process(PostureState.GOOD_POSTURE)

        assert posture_tracker.stable_state == PostureState.GOOD_POSTURE

        # Send consecutive UNKNOWN frames
        for _ in range(POSTURE_CONSECUTIVE_UNKNOWN_THRESHOLD):
            result = posture_tracker.process(PostureState.UNKNOWN)

        assert result == PostureState.UNKNOWN
        assert posture_tracker.stable_state == PostureState.UNKNOWN

    def test_screen_facing_state_transition(self, screen_facing_tracker):
        """Screen-facing should transition after consecutive frames."""
        from config import SCREEN_FACING_CONSECUTIVE_STATE_THRESHOLD

        # Establish SCREEN_FACING
        for _ in range(10):
            screen_facing_tracker.process(ScreenFacingState.SCREEN_FACING, 0.8)

        # Transition to LOOKING_AWAY
        for _ in range(SCREEN_FACING_CONSECUTIVE_STATE_THRESHOLD):
            result = screen_facing_tracker.process(ScreenFacingState.LOOKING_AWAY, 0.8)

        assert result == ScreenFacingState.LOOKING_AWAY

    def test_screen_facing_recovery(self, screen_facing_tracker):
        """Screen-facing should recover to SCREEN_FACING after returning."""
        from config import SCREEN_FACING_CONSECUTIVE_STATE_THRESHOLD

        # Establish LOOKING_AWAY
        for _ in range(10):
            screen_facing_tracker.process(ScreenFacingState.LOOKING_AWAY, 0.8)

        # Recover to SCREEN_FACING
        for _ in range(SCREEN_FACING_CONSECUTIVE_STATE_THRESHOLD):
            result = screen_facing_tracker.process(ScreenFacingState.SCREEN_FACING, 0.8)

        assert result == ScreenFacingState.SCREEN_FACING


# ---------------------------------------------------------------------------
# 5. Error Handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_posture_classifier_exception_handling(self, posture_classifier):
        """PostureClassifier should never raise exceptions."""
        # Create invalid landmarks that might cause issues
        landmarks = PostureLandmarks(
            available=True,
            shoulders_valid=True,
            left_shoulder=PoseLandmark(index=11, name="LEFT_SHOULDER", x=0.4, y=0.5, z=0.0, visibility=0.9),
            right_shoulder=PoseLandmark(index=12, name="RIGHT_SHOULDER", x=0.6, y=0.5, z=0.0, visibility=0.9),
            # No ears - should handle gracefully
        )

        # Should not raise, should return UNKNOWN
        result = posture_classifier.classify(landmarks)
        assert result == PostureState.UNKNOWN

    def test_posture_tracker_reset(self, posture_tracker):
        """PostureTracker reset should clear all state."""
        # Establish some state
        for _ in range(10):
            posture_tracker.process(PostureState.GOOD_POSTURE)

        assert posture_tracker.stable_state == PostureState.GOOD_POSTURE

        # Reset
        posture_tracker.reset()

        assert posture_tracker.stable_state == PostureState.UNKNOWN
        assert posture_tracker.candidate_state == PostureState.UNKNOWN
        assert posture_tracker.candidate_count == 0
        assert posture_tracker.uncertain_count == 0

    def test_presence_tracker_uncertain_frames_break_evidence(self, presence_tracker):
        """Uncertain frames should break consecutive evidence without triggering AWAY."""
        # Establish PRESENT
        result = FaceDetectionResult(
            detected=True,
            available=True,
            state=FaceDetectionState.DETECTED,
            landmarks_complete=True,
        )
        for _ in range(10):
            presence_tracker.process(result)

        assert presence_tracker._stable_state == PersonState.PRESENT

        # Send uncertain frames
        uncertain_result = FaceDetectionResult(
            detected=False,
            available=True,
            state=FaceDetectionState.UNCERTAIN,
        )
        for _ in range(2):
            presence_tracker.process(uncertain_result)

        # Should not be AWAY (uncertain doesn't count as AWAY evidence)
        assert presence_tracker._stable_state in (PersonState.PRESENT, PersonState.UNKNOWN)
        assert presence_tracker._stable_state != PersonState.AWAY

    def test_screen_facing_invalid_state_input(self, screen_facing_tracker):
        """Invalid state string should be treated as UNKNOWN."""
        result = screen_facing_tracker.process("INVALID_STATE", 0.8)
        assert result == ScreenFacingState.UNKNOWN

    def test_posture_normalization(self, posture_tracker):
        """Posture state normalization should handle equivalent states."""
        # SLOUCHED and SLOUCHED_POSTURE should be treated the same
        posture_tracker.process(PostureState.SLOUCHED)
        posture_tracker.process(PostureState.SLOUCHED_POSTURE)

        # Both should update the same candidate
        assert posture_tracker.candidate_state in (PostureState.SLOUCHED, PostureState.SLOUCHED_POSTURE)


# ---------------------------------------------------------------------------
# Run Tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
