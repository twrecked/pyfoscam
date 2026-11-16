"""Lossless AVI to MP4 remuxing and video metadata extraction."""
from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from .exceptions import FoscamMediaError

LOGGER = logging.getLogger(__package__)


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg executable is available on PATH."""
    return shutil.which("ffmpeg") is not None


def is_ffprobe_available() -> bool:
    """Check if ffprobe executable is available on PATH."""
    return shutil.which("ffprobe") is not None


async def convert_avi_to_mp4(
    source_avi: Path | str,
    dest_mp4: Path | str,
    timeout: int = 60,
    force_reencode: bool = False,
) -> bool:
    """Remux or transcode an AVI recording to MP4 asynchronously.

    Attempts stream copy (-c copy) first for near-instant conversion.
    Falls back to ultrafast H.264 re-encoding if stream copy fails.
    """
    source_avi = Path(source_avi)
    dest_mp4 = Path(dest_mp4)

    if not source_avi.is_file():
        raise FoscamMediaError(f"Source file does not exist: {source_avi}")

    dest_mp4.parent.mkdir(parents=True, exist_ok=True)
    if not is_ffmpeg_available():
        raise FoscamMediaError("ffmpeg is not installed or not found in PATH")

    # First attempt: fast lossless stream copy
    if not force_reencode:
        cmd_copy = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_avi),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(dest_mp4),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_copy,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if proc.returncode == 0 and dest_mp4.is_file() and dest_mp4.stat().st_size > 0:
                LOGGER.debug("Lossless remux succeeded for %s", dest_mp4.name)
                return True
            LOGGER.debug(
                "Lossless remux failed (rc=%s), falling back to re-encoding: %s",
                proc.returncode,
                stderr.decode(errors="ignore"),
            )
        except TimeoutError:
            LOGGER.warning("Lossless remux timed out for %s, falling back to re-encode", source_avi.name)
        except OSError as err:
            LOGGER.debug("Lossless remux error for %s: %s", source_avi.name, err)

    # Fallback attempt: re-encode video to H.264 / AAC
    cmd_encode = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_avi),
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(dest_mp4),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_encode,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode == 0 and dest_mp4.is_file() and dest_mp4.stat().st_size > 0:
            LOGGER.debug("Re-encode to MP4 succeeded for %s", dest_mp4.name)
            return True
        raise FoscamMediaError(
            f"ffmpeg conversion failed with code {proc.returncode}: {stderr.decode(errors='ignore')}"
        )
    except TimeoutError:
        raise FoscamMediaError(f"ffmpeg conversion timed out after {timeout} seconds for {source_avi.name}")
    except OSError as err:
        raise FoscamMediaError(f"ffmpeg conversion failed for {source_avi.name}: {err}") from err


async def get_video_duration(video_path: Path | str) -> int | None:
    """Probe video duration in seconds asynchronously using ffprobe."""
    if not is_ffprobe_available():
        return None

    video_path = Path(video_path)
    if not video_path.is_file():
        return None

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode == 0:
            val = float(stdout.decode().strip())
            return max(1, round(val))
    except (TimeoutError, OSError, ValueError) as err:
        LOGGER.debug("Failed getting duration for %s: %s", video_path, err)
    return None
