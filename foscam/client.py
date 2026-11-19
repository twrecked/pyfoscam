"""High-level asynchronous Foscam Camera client."""
from __future__ import annotations

import asyncio
import logging
import types
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Self
from urllib.parse import unquote, urlencode

import aiohttp

from .const import (
    DEFAULT_FOCUS_TRAVEL_TIME,
    DEFAULT_FTP_PORT,
    DEFAULT_PORT,
    DEFAULT_PTZ_TRAVEL_TIME,
    DEFAULT_RTSP_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_ZOOM_TRAVEL_TIME,
    FOCUS_COMMANDS,
    PTZ_COMMANDS,
    ZOOM_COMMANDS,
)
from .exceptions import (
    FoscamAuthError,
    FoscamCommandError,
    FoscamConnectionError,
    FoscamError,
)
from .ftp import FoscamFTPClient
from .media import FoscamMediaLibrary

LOGGER = logging.getLogger(__package__)


class FoscamCamera:
    """High-level asynchronous Foscam Camera device wrapper."""

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
        ssl: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.rtsp_port = rtsp_port
        self.ftp_port = ftp_port
        self.verbose = verbose
        self.ssl = ssl
        self.timeout = timeout
        self.storage_dir = Path(storage_dir) if storage_dir else Path.cwd() / "foscam"

        scheme = "https" if self.ssl else "http"
        self._base_url = f"{scheme}://{self.host}:{self.port}/cgi-bin/CGIProxy.fcgi"

        self._session = session
        self._own_session = session is None
        self._media: FoscamMediaLibrary | None = None
        self._dev_info: dict[str, Any] | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or initialize the aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        """Close internal session and resources."""
        if self._own_session and self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        await self.close()

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
        """Check return code from camera CGI response."""
        if code == 0:
            return
        if code in (-1, -8):
            raise FoscamConnectionError(
                f"{operation}: Device {self.host}:{self.port} returned error {code}"
            )
        if code == -2:
            raise FoscamAuthError(
                f"{operation}: Authentication failed for user '{self.username}'"
            )
        if code == -3:
            raise FoscamAuthError(
                f"{operation}: Permission denied (requires admin privileges)"
            )
        if code == -5:
            raise FoscamConnectionError(f"{operation}: Request timed out")
        raise FoscamCommandError(f"{operation} failed with error code: {code}")

    def _parse_xml_response(self, data: bytes) -> tuple[int, dict[str, str]]:
        """Parse Foscam XML CGI response."""
        try:
            root = ET.fromstring(data.decode("utf-8", errors="replace"))
        except ET.ParseError as err:
            raise FoscamCommandError(
                f"Failed to parse XML response from {self.host}: {err}"
            ) from err

        code = -7  # Unknown error code
        params: dict[str, str] = {}
        for child in root.iter():
            if child.tag == "result":
                try:
                    code = int(child.text.strip()) if child.text else -7
                except ValueError:
                    code = -7
            elif child.tag != "CGI_Result":
                params[child.tag] = unquote(child.text) if child.text is not None else ""

        return code, params

    async def _send_command(
        self,
        cmd: str,
        params: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> tuple[int, Any]:
        """Send an asynchronous CGI command to the camera."""
        session = await self._get_session()
        query_params: dict[str, str] = {
            "usr": self.username,
            "pwd": self.password,
            "cmd": cmd,
        }
        if params:
            for k, v in params.items():
                if v is not None:
                    query_params[k] = str(v)

        url = f"{self._base_url}?{urlencode(query_params)}"
        if self.verbose:
            LOGGER.debug("Sending CGI command to %s:%s (cmd=%s)", self.host, self.port, cmd)

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with session.get(url, timeout=timeout) as resp:
                if raw:
                    if resp.status != 200:
                        raise FoscamConnectionError(
                            f"HTTP {resp.status} executing {cmd} on {self.host}:{self.port}"
                        )
                    data = await resp.read()
                    if data.startswith(b"<") and b"<CGI_Result>" in data:
                        return self._parse_xml_response(data)
                    return 0, data

                data = await resp.read()
                return self._parse_xml_response(data)
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise FoscamConnectionError(
                f"CGI request '{cmd}' failed on {self.host}:{self.port}: {err}"
            ) from err

    async def get_info(self) -> dict[str, Any]:
        """Fetch device information (MAC address, model, firmware, etc)."""
        code, info = await self._send_command("getDevInfo")
        self._check_result(code, "getDevInfo")
        self._dev_info = dict(info) if info else {}

        # Optionally check ports
        try:
            p_code, port_info = await self._send_command("getPortInfo")
            if p_code == 0 and port_info and port_info.get("rtspPort"):
                self.rtsp_port = int(port_info["rtspPort"])
                self._dev_info["rtspPort"] = self.rtsp_port
        except FoscamError as err:
            LOGGER.debug("Port info query skipped for %s: %s", self.host, err)

        return self._dev_info

    @property
    def mac_address(self) -> str | None:
        """Return MAC address of camera if cached."""
        if self._dev_info and "mac" in self._dev_info:
            return self._dev_info["mac"]
        return None

    async def get_state(self) -> dict[str, Any]:
        """Fetch current camera runtime state."""
        code, dev_state = await self._send_command("getDevState")
        self._check_result(code, "getDevState")

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

    async def start_ftp_server(self, settle_time: float = 1.0) -> None:
        """Ensure FTP service is active on the camera."""
        code, _ = await self._send_command("startFtpServer")
        LOGGER.debug("startFtpServer executed with code %s", code)
        if settle_time > 0:
            await asyncio.sleep(settle_time)

    async def get_snapshot(self) -> bytes:
        """Capture a still snapshot and return raw JPEG bytes."""
        code, data = await self._send_command("snapPicture2", raw=True)
        self._check_result(code, "snapPicture2")
        if not data or not isinstance(data, (bytes, bytearray)):
            raise FoscamCommandError("Snapshot returned empty data")
        return bytes(data)

    async def enable_motion_detection(self) -> None:
        """Enable motion detection alarm."""
        code, config = await self._send_command("getMotionDetectConfig")
        if code == 0 and config:
            config["isEnable"] = "1"
            code2, _ = await self._send_command("setMotionDetectConfig", config)
            self._check_result(code2, "setMotionDetectConfig")
            return

        # Fallback for devices supporting getMotionDetectConfig1 (e.g. FI9900P)
        code, config = await self._send_command("getMotionDetectConfig1")
        if code == 0 and config:
            config["isEnable"] = "1"
            code2, _ = await self._send_command("setMotionDetectConfig1", config)
            self._check_result(code2, "setMotionDetectConfig1")
            return

        self._check_result(code, "enable_motion_detection")

    async def disable_motion_detection(self) -> None:
        """Disable motion detection alarm."""
        code, config = await self._send_command("getMotionDetectConfig")
        if code == 0 and config:
            config["isEnable"] = "0"
            code2, _ = await self._send_command("setMotionDetectConfig", config)
            self._check_result(code2, "setMotionDetectConfig")
            return

        # Fallback for devices supporting getMotionDetectConfig1
        code, config = await self._send_command("getMotionDetectConfig1")
        if code == 0 and config:
            config["isEnable"] = "0"
            code2, _ = await self._send_command("setMotionDetectConfig1", config)
            self._check_result(code2, "setMotionDetectConfig1")
            return

        self._check_result(code, "disable_motion_detection")

    async def ptz(self, movement: str, travel_time: float = DEFAULT_PTZ_TRAVEL_TIME) -> None:
        """Execute a pan/tilt action for travel_time seconds."""
        movement = movement.lower().strip()
        cmd_name = PTZ_COMMANDS.get(movement)
        if not cmd_name:
            valid = ", ".join(PTZ_COMMANDS.keys())
            raise FoscamCommandError(f"Invalid movement '{movement}'. Valid: {valid}")

        code, _ = await self._send_command(cmd_name)
        self._check_result(code, f"ptz({movement})")

        if travel_time > 0:
            try:
                await asyncio.sleep(travel_time)
            finally:
                await self.ptz_stop()

    async def ptz_stop(self) -> None:
        """Stop PTZ movement."""
        code, _ = await self._send_command("ptzStopRun")
        self._check_result(code, "ptzStopRun")

    async def zoom(self, direction: str, travel_time: float = DEFAULT_ZOOM_TRAVEL_TIME) -> None:
        """Execute an optical zoom action for travel_time seconds."""
        direction = direction.lower().strip()
        cmd_name = ZOOM_COMMANDS.get(direction)
        if not cmd_name:
            valid = ", ".join(ZOOM_COMMANDS.keys())
            raise FoscamCommandError(f"Invalid zoom direction '{direction}'. Valid: {valid}")

        code, _ = await self._send_command(cmd_name)
        self._check_result(code, f"zoom({direction})")

        if travel_time > 0:
            try:
                await asyncio.sleep(travel_time)
            finally:
                await self.zoom_stop()

    async def zoom_stop(self) -> None:
        """Stop optical zoom movement."""
        code, _ = await self._send_command("zoomStop")
        self._check_result(code, "zoomStop")

    async def focus(self, direction: str, travel_time: float = DEFAULT_FOCUS_TRAVEL_TIME) -> None:
        """Execute a manual focus action for travel_time seconds."""
        direction = direction.lower().strip()
        cmd_name = FOCUS_COMMANDS.get(direction)
        if not cmd_name:
            valid = ", ".join(FOCUS_COMMANDS.keys())
            raise FoscamCommandError(f"Invalid focus direction '{direction}'. Valid: {valid}")

        code, _ = await self._send_command(cmd_name)
        self._check_result(code, f"focus({direction})")

        if travel_time > 0:
            try:
                await asyncio.sleep(travel_time)
            finally:
                await self.focus_stop()

    async def focus_stop(self) -> None:
        """Stop focus movement."""
        code, _ = await self._send_command("focusStop")
        self._check_result(code, "focusStop")

    async def ptz_preset(self, preset_name: str) -> None:
        """Go to PTZ preset."""
        code, _ = await self._send_command("ptzGotoPresetPoint", {"name": preset_name})
        self._check_result(code, f"ptzGotoPresetPoint({preset_name})")

    async def get_ptz_presets(self) -> list[str]:
        """Fetch list of saved PTZ preset names from camera."""
        code, res = await self._send_command("getPTZPresetPointList")
        if code != 0 or not res:
            return []
        presets: list[str] = []
        for k, v in res.items():
            if k.startswith("point") and v and v.strip():
                presets.append(v.strip())
        return presets

    def rtsp_url(self, stream: str = "Main") -> str:
        """Return RTSP live stream URL."""
        return f"rtsp://{self.username}:{self.password}@{self.host}:{self.rtsp_port}/video{stream}"

    async def is_asleep(self) -> bool:
        """Check if camera is in sleep / privacy mode."""
        code, res = await self._send_command("getAlexaState")
        self._check_result(code, "getAlexaState")
        return (res or {}).get("state") == "1"

    async def sleep(self) -> None:
        """Put camera into sleep / privacy mode."""
        code, _ = await self._send_command("alexaSleep")
        self._check_result(code, "alexaSleep")

    async def wake_up(self) -> None:
        """Wake camera from sleep / privacy mode."""
        code, _ = await self._send_command("alexaWakeUp")
        self._check_result(code, "alexaWakeUp")

    async def get_led_state(self) -> bool:
        """Get camera physical status LED state (True if enabled)."""
        code, res = await self._send_command("getLedEnableState")
        self._check_result(code, "getLedEnableState")
        return (res or {}).get("isEnable") == "1"

    async def set_led_state(self, enabled: bool) -> None:
        """Enable or disable camera physical status LED."""
        code, _ = await self._send_command(
            "setLedEnableState", {"isEnable": "1" if enabled else "0"}
        )
        self._check_result(code, "setLedEnableState")

    async def get_flip_and_mirror(self) -> dict[str, bool]:
        """Get video flip and mirror settings."""
        code, res = await self._send_command("getMirrorAndFlipSetting")
        self._check_result(code, "getMirrorAndFlipSetting")
        res_dict = res or {}
        return {
            "is_flip": res_dict.get("isFlip") == "1",
            "is_mirror": res_dict.get("isMirror") == "1",
        }

    async def set_flip(self, flip: bool) -> None:
        """Set video vertical flip."""
        code, _ = await self._send_command(
            "flipVideo", {"isFlip": "1" if flip else "0"}
        )
        self._check_result(code, "flipVideo")

    async def set_mirror(self, mirror: bool) -> None:
        """Set video horizontal mirror."""
        code, _ = await self._send_command(
            "mirrorVideo", {"isMirror": "1" if mirror else "0"}
        )
        self._check_result(code, "mirrorVideo")

    async def get_infra_led_config(self) -> dict[str, Any]:
        """Get infrared LED night vision configuration."""
        code, res = await self._send_command("getInfraLedConfig")
        self._check_result(code, "getInfraLedConfig")
        res_dict = res or {}
        mode_str = res_dict.get("mode", "0")
        try:
            mode = int(mode_str)
        except ValueError:
            mode = 0
        return {
            "mode": mode,
            "auto": mode == 0,
            "raw": res_dict,
        }

    async def set_infra_led_config(self, mode: int) -> None:
        """Set infrared LED mode (0 = Auto, 1 = Manual)."""
        code, _ = await self._send_command("setInfraLedConfig", {"mode": str(mode)})
        self._check_result(code, "setInfraLedConfig")

    async def open_infra_led(self) -> None:
        """Force open infrared LED."""
        code, _ = await self._send_command("openInfraLed")
        self._check_result(code, "openInfraLed")

    async def close_infra_led(self) -> None:
        """Force close infrared LED."""
        code, _ = await self._send_command("closeInfraLed")
        self._check_result(code, "closeInfraLed")

    async def set_infra_led(self, mode_or_state: str | bool) -> None:
        """Set infrared LED mode or force state ('auto', 'on', 'off' or bool)."""
        if isinstance(mode_or_state, str):
            val = mode_or_state.lower().strip()
            if val == "auto":
                await self.set_infra_led_config(0)
            elif val in ("on", "open", "true", "1"):
                await self.set_infra_led_config(1)
                await self.open_infra_led()
            elif val in ("off", "close", "false", "0"):
                await self.set_infra_led_config(1)
                await self.close_infra_led()
            else:
                raise FoscamCommandError(
                    f"Invalid infra led state '{mode_or_state}'. Use 'auto', 'on', or 'off'."
                )
        elif mode_or_state:
            await self.set_infra_led_config(1)
            await self.open_infra_led()
        else:
            await self.set_infra_led_config(0)

    async def get_volume(self) -> int:
        """Get camera audio volume (0-100)."""
        code, res = await self._send_command("getAudioVolume")
        self._check_result(code, "getAudioVolume")
        try:
            return int((res or {}).get("volume", 0))
        except ValueError:
            return 0

    async def set_volume(self, volume: int) -> None:
        """Set camera audio volume (0-100)."""
        clamped = max(0, min(100, int(volume)))
        code, _ = await self._send_command("setAudioVolume", {"volume": str(clamped)})
        self._check_result(code, "setAudioVolume")

    async def get_voice_state(self) -> bool:
        """Get camera voice/audio enabled state (True if sound output is enabled)."""
        code, res = await self._send_command("getVoiceEnableState")
        self._check_result(code, "getVoiceEnableState")
        return (res or {}).get("isEnable") == "1"

    async def set_voice_state(self, enabled: bool) -> None:
        """Enable or disable camera audio voice output."""
        code, _ = await self._send_command(
            "setVoiceEnableState", {"isEnable": "1" if enabled else "0"}
        )
        self._check_result(code, "setVoiceEnableState")

    async def get_speak_volume(self) -> int:
        """Get speak volume (0-100)."""
        code, res = await self._send_command("getSpeakVolume")
        self._check_result(code, "getSpeakVolume")
        try:
            return int((res or {}).get("SpeakVolume", 0))
        except ValueError:
            return 0

    async def set_speak_volume(self, volume: int) -> None:
        """Set speak volume (0-100)."""
        clamped = max(0, min(100, int(volume)))
        code, _ = await self._send_command(
            "setSpeakVolume", {"SpeakVolume": str(clamped)}
        )
        self._check_result(code, "setSpeakVolume")

    async def open_white_light(self) -> None:
        """Turn on camera white light / spotlight."""
        code, _ = await self._send_command("openWhiteLight")
        self._check_result(code, "openWhiteLight")

    async def close_white_light(self) -> None:
        """Turn off camera white light / spotlight."""
        code, _ = await self._send_command("closeWhiteLight")
        self._check_result(code, "closeWhiteLight")

    async def get_white_light_brightness(self) -> dict[str, Any]:
        """Get camera white light configuration."""
        code, res = await self._send_command("getWhiteLightBrightness")
        self._check_result(code, "getWhiteLightBrightness")
        return dict(res or {})

    async def get_siren_config(self) -> dict[str, Any]:
        """Get siren alarm configuration."""
        code, res = await self._send_command("getSirenConfig")
        self._check_result(code, "getSirenConfig")
        return dict(res or {})

    async def set_siren_config(
        self, enable: bool, volume: int = 100, reserved: int = 0
    ) -> None:
        """Set siren alarm configuration."""
        clamped_vol = max(0, min(100, int(volume)))
        params = {
            "sirenEnable": "1" if enable else "0",
            "sirenvolume": str(clamped_vol),
            "reserved": str(reserved),
        }
        code, _ = await self._send_command("setSirenConfig", params)
        self._check_result(code, "setSirenConfig")

    async def get_full_state(self) -> dict[str, Any]:
        """Fetch complete camera state including alarms, sleep, LED, volume, flip, and IR."""
        results = await asyncio.gather(
            self.get_state(),
            self.is_asleep(),
            self.get_led_state(),
            self.get_flip_and_mirror(),
            self.get_infra_led_config(),
            self.get_volume(),
            self.get_voice_state(),
            self.get_white_light_brightness(),
            self.get_siren_config(),
            return_exceptions=True,
        )

        state = results[0] if isinstance(results[0], dict) else {}
        sleep = results[1] if isinstance(results[1], bool) else None
        led = results[2] if isinstance(results[2], bool) else None
        mf = results[3] if isinstance(results[3], dict) else {}
        ir = results[4] if isinstance(results[4], dict) else {}
        vol = results[5] if isinstance(results[5], int) else None
        voice = results[6] if isinstance(results[6], bool) else None
        white_light = results[7] if isinstance(results[7], dict) else None
        siren = results[8] if isinstance(results[8], dict) else None

        return {
            **state,
            "is_asleep": sleep,
            "led_enabled": led,
            "is_flip": mf.get("is_flip"),
            "is_mirror": mf.get("is_mirror"),
            "infra_led_mode": ir.get("mode"),
            "infra_led_auto": ir.get("auto"),
            "volume": vol,
            "voice_enabled": voice,
            "white_light": white_light,
            "siren": siren,
        }
