"""High-level Foscam Camera client."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from libpyfoscam import FoscamCamera as _RawFoscamCamera

from .const import (
    DEFAULT_FTP_PORT,
    DEFAULT_PORT,
    DEFAULT_PTZ_TRAVEL_TIME,
    DEFAULT_RTSP_PORT,
    PTZ_COMMANDS,
)
from .exceptions import (
    FoscamAuthError,
    FoscamCommandError,
    FoscamConnectionError,
)
from .ftp import FoscamFTPClient
from .media import FoscamMediaLibrary

LOGGER = logging.getLogger(__package__)


class FoscamCamera:
    """High-level Foscam Camera device wrapper."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = DEFAULT_PORT,
        rtsp_port: int = DEFAULT_RTSP_PORT,
        ftp_port: int = DEFAULT_FTP_PORT,
        storage_dir: Path | str | None = None,
        verbose: bool = False,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.rtsp_port = rtsp_port
        self.ftp_port = ftp_port
        self.verbose = verbose
        self.storage_dir = Path(storage_dir) if storage_dir else Path.cwd() / "foscam"

        self._raw_cam = _RawFoscamCamera(
            host=self.host,
            port=self.port,
            usr=self.username,
            pwd=self.password,
            verbose=self.verbose,
        )

        self._media: FoscamMediaLibrary | None = None
        self._dev_info: dict[str, Any] | None = None

    @property
    def media(self) -> FoscamMediaLibrary:
        """Access the camera's media recording library."""
        if self._media is None:
            self._media = FoscamMediaLibrary(self, storage_dir=self.storage_dir)
        return self._media

    def get_ftp_client(self) -> FoscamFTPClient:
        """Create an FTP client for this camera."""
        return FoscamFTPClient(
            host=self.host,
            username=self.username,
            password=self.password,
            port=self.ftp_port,
        )

    def _check_result(self, code: int, operation: str) -> None:
        """Check return code from libpyfoscam."""
        if code == 0:
            return
        if code == -1:
            raise FoscamConnectionError(f"{operation}: Device {self.host}:{self.port} is unavailable")
        if code == -2:
            raise FoscamAuthError(f"{operation}: Authentication failed for user '{self.username}'")
        if code == -3:
            raise FoscamAuthError(f"{operation}: Permission denied (requires admin privileges)")
        raise FoscamCommandError(f"{operation} failed with error code: {code}")

    def get_info(self) -> dict[str, Any]:
        """Fetch device information (MAC address, model, firmware, etc)."""
        code, info = self._raw_cam.get_dev_info()
        self._check_result(code, "get_dev_info")
        self._dev_info = dict(info) if info else {}

        # Optionally check ports
        try:
            p_code, port_info = self._raw_cam.get_port_info()
            if p_code == 0 and port_info:
                if "rtspPort" in port_info and port_info["rtspPort"]:
                    self.rtsp_port = int(port_info["rtspPort"])
                    self._dev_info["rtspPort"] = self.rtsp_port
        except Exception:
            pass

        return self._dev_info

    @property
    def mac_address(self) -> str | None:
        """Return MAC address of camera."""
        if self._dev_info and "mac" in self._dev_info:
            return self._dev_info["mac"]
        try:
            info = self.get_info()
            return info.get("mac")
        except Exception:
            return None

    def get_state(self) -> dict[str, Any]:
        """Fetch current camera runtime state."""
        code, dev_state = self._raw_cam.get_dev_state()
        self._check_result(code, "get_dev_state")

        state_dict = dict(dev_state) if dev_state else {}

        motion_alarm = state_dict.get("motionDetectAlarm", "0")
        sound_alarm = state_dict.get("soundAlarm", "0")
        io_alarm = state_dict.get("IOAlarm", "0")
        recording_val = state_dict.get("recording", state_dict.get("record", "0"))

        return {
            "motion_detected": motion_alarm == "2",
            "motion_enabled": motion_alarm != "0",
            "sound_detected": sound_alarm == "2",
            "sound_enabled": sound_alarm != "0",
            "io_detected": io_alarm == "2",
            "io_enabled": io_alarm != "0",
            "is_recording": recording_val == "1",
            "raw": state_dict,
        }

    def start_ftp_server(self, settle_time: float = 1.0) -> None:
        """Ensure FTP service is active on the camera."""
        code, _ = self._raw_cam.execute_command("startFtpServer")
        LOGGER.debug("startFtpServer executed with code %s", code)
        if settle_time > 0:
            time.sleep(settle_time)

    def get_snapshot(self) -> bytes:
        """Capture a still snapshot and return raw JPEG bytes."""
        code, data = self._raw_cam.snap_picture_2()
        self._check_result(code, "snap_picture_2")
        if not data:
            raise FoscamCommandError("Snapshot returned empty data")
        return data

    def enable_motion_detection(self) -> None:
        """Enable motion detection alarm."""
        code = self._raw_cam.enable_motion_detection()
        self._check_result(code, "enable_motion_detection")

    def disable_motion_detection(self) -> None:
        """Disable motion detection alarm."""
        code = self._raw_cam.disable_motion_detection()
        self._check_result(code, "disable_motion_detection")

    def ptz(self, movement: str, travel_time: float = DEFAULT_PTZ_TRAVEL_TIME) -> None:
        """Execute a pan/tilt action for travel_time seconds."""
        movement = movement.lower().strip()
        cmd_name = PTZ_COMMANDS.get(movement)
        if not cmd_name:
            valid = ", ".join(PTZ_COMMANDS.keys())
            raise FoscamCommandError(f"Invalid movement '{movement}'. Valid: {valid}")

        func = getattr(self._raw_cam, cmd_name)
        code, _ = func()
        self._check_result(code, f"ptz({movement})")

        if travel_time > 0:
            time.sleep(travel_time)
            stop_code, _ = self._raw_cam.ptz_stop_run()
            self._check_result(stop_code, "ptz_stop_run")

    def ptz_stop(self) -> None:
        """Stop PTZ movement."""
        code, _ = self._raw_cam.ptz_stop_run()
        self._check_result(code, "ptz_stop_run")

    def ptz_preset(self, preset_name: str) -> None:
        """Go to PTZ preset."""
        code, _ = self._raw_cam.ptz_goto_preset(preset_name)
        self._check_result(code, f"ptz_goto_preset({preset_name})")

    def rtsp_url(self, stream: str = "Main") -> str:
        """Return RTSP live stream URL."""
        return f"rtsp://{self.username}:{self.password}@{self.host}:{self.rtsp_port}/video{stream}"
