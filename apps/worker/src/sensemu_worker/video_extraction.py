import json
import subprocess
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path


class VideoExtractionError(RuntimeError):
    pass


def probe_video(video_path: Path) -> tuple[int, int, int]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        duration_ms = max(1, round(float(payload["format"]["duration"]) * 1000))
        return int(stream["width"]), int(stream["height"]), duration_ms
    except (FileNotFoundError, subprocess.SubprocessError, KeyError, ValueError, IndexError) as error:
        raise VideoExtractionError("无法读取视频文件，请确认 ffmpeg 已安装且视频格式有效") from error


def extract_frames(
    video_path: Path,
    output_directory: Path,
    *,
    frame_interval_ms: int,
    deduplicate: bool,
    on_progress: Callable[[int], None] | None = None,
) -> tuple[list[Path], tuple[int, int], int]:
    width, height, duration_ms = probe_video(video_path)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_pattern = output_directory / "frame-%06d.jpg"
    filters = [f"fps=1000/{frame_interval_ms}"]
    if deduplicate:
        filters.insert(0, "mpdecimate")
    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        ",".join(filters),
        "-q:v",
        "2",
        "-vsync",
        "vfr",
        str(output_pattern),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=60 * 60)
    except FileNotFoundError as error:
        raise VideoExtractionError("当前 Worker 未安装 ffmpeg") from error
    except subprocess.TimeoutExpired as error:
        raise VideoExtractionError("视频抽帧超时") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "视频抽帧失败")[-2000:]
        raise VideoExtractionError(detail) from error

    frames = sorted(output_directory.glob("frame-*.jpg"))
    if not frames:
        raise VideoExtractionError("视频没有生成可用画面")
    if len(frames) > 20_000:
        raise VideoExtractionError("单个视频最多生成 20,000 张画面，请增大抽帧间隔")
    if on_progress:
        on_progress(75)
    return frames, (width, height), duration_ms


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
