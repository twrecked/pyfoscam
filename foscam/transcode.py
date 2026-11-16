"""Transcoding and media utilities using ffmpeg/ffprobe."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from .exceptions import FoscamMediaError

LOGGER = logging.getLogger(__package__)


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg is in PATH."""
    return shutil.which("ffmpeg") is not None


def is_ffprobe_available() -> bool:
    """Check if ffprobe is in PATH."""
    return shutil.which("ffprobe") is not None


def get_video_duration(video_path: Path | str) -> int | None:
    """Get video duration in seconds via ffprobe."""
    if not is_ffprobe_available():
        return None

    video_path = str(video_path)
    if not os.path.isfile(video_path):
        return None

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            return int(float(res.stdout.strip()))
    except Exception as err:
        LOGGER.debug("Failed getting duration for %s: %s", video_path, err)

    return None


def convert_avi_to_mp4(
    src_path: Path | str,
    dst_path: Path | str,
    stream_copy_only: bool = False,
) -> None:
    """Convert an AVI file to MP4 using ffmpeg.

    Tries fast stream-copy first (-c copy). Falls back to H.264 encode if needed.
    """
    if not is_ffmpeg_available():
        raise FoscamMediaError("ffmpeg is not installed or not available in PATH")

    src = str(src_path)
    dst = str(dst_path)

    if not os.path.isfile(src):
        raise FoscamMediaError(f"Source file not found: {src}")

    # Ensure destination directory exists
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)

    # 1. Try fast stream copy
    copy_cmd = ["ffmpeg", "-y", "-i", src, "-c", "copy", "-movflags", "+faststart", dst]
    res = subprocess.run(copy_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 0:
        return

    # If stream copy failed or produced empty file
    if os.path.exists(dst):
        try:
            os.unlink(dst)
        except OSError:
            pass

    if stream_copy_only:
        raise FoscamMediaError(f"Stream copy remux failed for {src}: {res.stderr}")

    # 2. Fall back to re-encoding
    LOGGER.debug("Stream copy failed, falling back to re-encode for %s", src)
    encode_cmd = ["ffmpeg", "-y", "-i", src, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst]
    res_enc = subprocess.run(encode_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res_enc.returncode != 0:
        if os.path.exists(dst):
            try:
                os.unlink(dst)
            except OSError:
                pass
        raise FoscamMediaError(f"FFmpeg transcode failed for {src}: {res_enc.stderr}")
