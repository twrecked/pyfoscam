"""pyfoscam: Python library and CLI for Foscam IP cameras."""
from __future__ import annotations

from .client import FoscamCamera as FoscamCamera
from .config import (
    get_camera_config as get_camera_config,
)
from .config import (
    load_config as load_config,
)
from .config import (
    remove_camera_config as remove_camera_config,
)
from .config import (
    set_camera_config as set_camera_config,
)
from .exceptions import (
    FoscamAuthError as FoscamAuthError,
)
from .exceptions import (
    FoscamCommandError as FoscamCommandError,
)
from .exceptions import (
    FoscamConfigError as FoscamConfigError,
)
from .exceptions import (
    FoscamConnectionError as FoscamConnectionError,
)
from .exceptions import (
    FoscamError as FoscamError,
)
from .exceptions import (
    FoscamMediaError as FoscamMediaError,
)
from .ftp import FoscamFTPClient as FoscamFTPClient
from .media import (
    FoscamMediaLibrary as FoscamMediaLibrary,
)
from .media import (
    FoscamRecording as FoscamRecording,
)
from .media import (
    prune_local_recordings as prune_local_recordings,
)
from .transcode import (
    convert_avi_to_mp4 as convert_avi_to_mp4,
)
from .transcode import (
    is_ffmpeg_available as is_ffmpeg_available,
)

__version__ = "0.1.0-alpha.1"
__all__ = [
    "FoscamAuthError",
    "FoscamCamera",
    "FoscamCommandError",
    "FoscamConfigError",
    "FoscamConnectionError",
    "FoscamError",
    "FoscamFTPClient",
    "FoscamMediaError",
    "FoscamMediaLibrary",
    "FoscamRecording",
    "convert_avi_to_mp4",
    "get_camera_config",
    "is_ffmpeg_available",
    "load_config",
    "prune_local_recordings",
    "remove_camera_config",
    "set_camera_config",
]
