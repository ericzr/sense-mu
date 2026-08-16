import json
import subprocess
from pathlib import Path

import pytest

from sensemu_worker.video_extraction import VideoExtractionError, extract_frames, probe_video


def test_probe_video_reads_dimensions_and_duration(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        del args, kwargs
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {"streams": [{"width": 1920, "height": 1080}], "format": {"duration": "4.25"}}
            ),
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert probe_video(tmp_path / "source.mp4") == (1920, 1080, 4250)


def test_extract_frames_uses_interval_and_deduplication(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        del kwargs
        calls.append(command)
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=json.dumps(
                    {"streams": [{"width": 640, "height": 360}], "format": {"duration": "2"}}
                ),
            )
        output_pattern = Path(command[-1])
        output_pattern.parent.mkdir(parents=True, exist_ok=True)
        (output_pattern.parent / "frame-000001.jpg").write_bytes(b"one")
        (output_pattern.parent / "frame-000002.jpg").write_bytes(b"two")
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    frames, dimensions, duration_ms = extract_frames(
        tmp_path / "source.mp4",
        tmp_path / "frames",
        frame_interval_ms=500,
        deduplicate=True,
    )
    assert len(frames) == 2
    assert dimensions == (640, 360)
    assert duration_ms == 2000
    assert "mpdecimate,fps=1000/500" in calls[1]


def test_extract_frames_reports_missing_ffmpeg(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        del kwargs
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout=json.dumps(
                    {"streams": [{"width": 640, "height": 360}], "format": {"duration": "2"}}
                ),
            )
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(VideoExtractionError, match="未安装 ffmpeg"):
        extract_frames(
            tmp_path / "source.mp4",
            tmp_path / "frames",
            frame_interval_ms=1000,
            deduplicate=False,
        )
