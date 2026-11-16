"""pyfoscam: Python library and CLI for Foscam IP cameras."""

from .client import FoscamCamera
from .config import get_camera_config, load_config, remove_camera_config, set_camera_config
from .exceptions import (
    FoscamAuthError,
    FoscamCommandError,
    FoscamConfigError,
    FoscamConnectionError,
    FoscamError,
    FoscamMediaError,
)
from .ftp import FoscamFTPClient
from .media import FoscamMediaLibrary, FoscamRecording
from .transcode import convert_avi_to_mp4, is_ffmpeg_available

__version__ = "0.1.0"
__all__ = [
    "FoscamCamera",
    "FoscamMediaLibrary",
    "FoscamRecording",
    "FoscamFTPClient",
    "FoscamError",
    "FoscamAuthError",
    "FoscamConnectionError",
    "FoscamCommandError",
    "FoscamMediaError",
    "FoscamConfigError",
    "load_config",
    "set_camera_config",
    "get_camera_config",
    "remove_camera_config",
    "convert_avi_to_mp4",
    "is_ffmpeg_available",
]
