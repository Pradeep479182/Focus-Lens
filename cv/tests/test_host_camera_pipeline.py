"""Reliability tests for Tauri-hosted camera frame input."""

import base64
import io
import json
import sys

import cv2
import numpy as np

from app.pipeline import CVPipeline


class FakeCamera:
    def __init__(self):
        self.released = False

    def release(self):
        self.released = True


class FakeProcessor:
    def __init__(self, fail=False):
        self.frames = []
        self.closed = False
        self.fail = fail

    def process(self, frame):
        if self.fail:
            raise RuntimeError("frame processing failed")
        self.frames.append(frame)
        return frame

    def close(self):
        self.closed = True


class FakeAggregator:
    def update(self, _frame_result):
        return {
            "person_presence": "PRESENT",
            "screen_facing": "SCREEN_FACING",
            "posture": "GOOD_POSTURE",
            "confidence": 0.9,
            "frame": "must not be emitted",
        }


def make_pipeline(fail=False):
    pipeline = CVPipeline.__new__(CVPipeline)
    pipeline._running = False
    pipeline._camera = FakeCamera()
    pipeline._processor = FakeProcessor(fail=fail)
    pipeline._aggregator = FakeAggregator()
    pipeline._headless = True
    pipeline._preview = None
    return pipeline


def make_frame_message(frame_index=4):
    image = np.full((48, 64, 3), 127, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return {
        "frame_index": frame_index,
        "width": 64,
        "height": 48,
        "jpeg_base64": base64.b64encode(encoded).decode("ascii"),
    }


def test_host_camera_mode_processes_valid_frames_and_emits_only_derived_signals(monkeypatch, capsys):
    message = make_frame_message()
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(message) + "\n"))
    pipeline = make_pipeline()

    pipeline.run_from_stdin()

    assert pipeline._camera.released
    assert pipeline._processor.closed
    assert len(pipeline._processor.frames) == 1
    frame = pipeline._processor.frames[0]
    assert frame.frame_index == 4
    assert frame.data.shape == (48, 64, 3)

    signal = json.loads(capsys.readouterr().out)
    assert signal["person_presence"] == "PRESENT"
    assert "frame" not in signal
    assert "jpeg_base64" not in signal


def test_host_camera_mode_ignores_invalid_frame_messages(monkeypatch, capsys):
    invalid_messages = [
        "{not json}",
        json.dumps({**make_frame_message(), "jpeg_base64": "%%%"}),
        json.dumps({**make_frame_message(), "width": 32}),
    ]
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n".join(invalid_messages) + "\n"))
    pipeline = make_pipeline()

    pipeline.run_from_stdin()

    assert pipeline._processor.frames == []
    assert pipeline._camera.released
    assert pipeline._processor.closed
    assert capsys.readouterr().out == ""


def test_host_camera_mode_emits_cv_failure_and_releases_processor(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps(make_frame_message()) + "\n"),
    )
    pipeline = make_pipeline(fail=True)

    pipeline.run_from_stdin()

    assert pipeline._camera.released
    assert pipeline._processor.closed
    response = json.loads(capsys.readouterr().out)
    assert response["__type"] == "cv_status"
    assert response["status"] == "failed"
    assert response["error"] == "frame processing failed"
