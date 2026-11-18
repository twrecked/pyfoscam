"""Tests for high-level asynchronous FoscamCamera client."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from foscam.client import FoscamCamera
from foscam.exceptions import FoscamAuthError, FoscamCommandError, FoscamConnectionError


def test_rtsp_url():
    cam = FoscamCamera("192.168.1.50", "admin", "secret", port=88, rtsp_port=554)
    assert cam.rtsp_url("Main") == "rtsp://admin:secret@192.168.1.50:554/videoMain"
    assert cam.rtsp_url("Sub") == "rtsp://admin:secret@192.168.1.50:554/videoSub"


@pytest.mark.asyncio
async def test_get_state():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    mock_raw_state = {
        "motionDetectAlarm": "2",
        "soundAlarm": "0",
        "IOAlarm": "0",
        "recording": "1",
    }
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, mock_raw_state)
        state = await cam.get_state()
        assert state["motion_detected"] is True
        assert state["motion_enabled"] is True
        assert state["sound_detected"] is False
        assert state["sound_enabled"] is False
        assert state["is_recording"] is True
        mock_send.assert_awaited_once_with("getDevState")


@pytest.mark.asyncio
async def test_error_handling():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")

    # Connection error (-1)
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (-1, None)
        with pytest.raises(FoscamConnectionError):
            await cam.get_info()

    # Auth error (-2)
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (-2, None)
        with pytest.raises(FoscamAuthError):
            await cam.get_info()

    # Permission denied (-3)
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (-3, None)
        with pytest.raises(FoscamAuthError):
            await cam.get_info()

    # Command error (other non-zero)
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (100, None)
        with pytest.raises(FoscamCommandError):
            await cam.get_info()


@pytest.mark.asyncio
async def test_ptz():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_send.return_value = (0, {})
        await cam.ptz("up", travel_time=0.1)
        assert mock_send.await_count == 2
        mock_send.assert_any_await("ptzMoveUp")
        mock_send.assert_any_await("ptzStopRun")
        mock_sleep.assert_awaited_once_with(0.1)

    # Invalid movement
    with pytest.raises(FoscamCommandError):
        await cam.ptz("invalid_direction")


@pytest.mark.asyncio
async def test_http_cgi_parsing():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    xml_response = (
        b"<CGI_Result>\n"
        b"<result>0</result>\n"
        b"<modelName>FI9821W</modelName>\n"
        b"<mac>001122334455</mac>\n"
        b"</CGI_Result>"
    )
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read.return_value = xml_response

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_resp
    mock_session.get.return_value.__aexit__.return_value = None

    with patch.object(cam, "_get_session", new_callable=AsyncMock) as mock_get_sess:
        mock_get_sess.return_value = mock_session
        info = await cam.get_info()
        assert info["modelName"] == "FI9821W"
        assert info["mac"] == "001122334455"
        assert cam.mac_address == "001122334455"


@pytest.mark.asyncio
async def test_snapshot():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 20
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read.return_value = fake_jpeg

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_resp
    mock_session.get.return_value.__aexit__.return_value = None

    with patch.object(cam, "_get_session", new_callable=AsyncMock) as mock_get_sess:
        mock_get_sess.return_value = mock_session
        data = await cam.get_snapshot()
        assert data == fake_jpeg


@pytest.mark.asyncio
async def test_sleep_and_wake():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {"state": "1"})
        assert await cam.is_asleep() is True
        mock_send.assert_awaited_once_with("getAlexaState")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.sleep()
        mock_send.assert_awaited_once_with("alexaSleep")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.wake_up()
        mock_send.assert_awaited_once_with("alexaWakeUp")


@pytest.mark.asyncio
async def test_led_state():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {"isEnable": "1"})
        assert await cam.get_led_state() is True
        mock_send.assert_awaited_once_with("getLedEnableState")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.set_led_state(False)
        mock_send.assert_awaited_once_with("setLedEnableState", {"isEnable": "0"})


@pytest.mark.asyncio
async def test_flip_and_mirror():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {"isFlip": "1", "isMirror": "0"})
        res = await cam.get_flip_and_mirror()
        assert res == {"is_flip": True, "is_mirror": False}
        mock_send.assert_awaited_once_with("getMirrorAndFlipSetting")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.set_flip(True)
        mock_send.assert_awaited_once_with("flipVideo", {"isFlip": "1"})

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.set_mirror(False)
        mock_send.assert_awaited_once_with("mirrorVideo", {"isMirror": "0"})


@pytest.mark.asyncio
async def test_infra_led():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {"mode": "0"})
        res = await cam.get_infra_led_config()
        assert res["mode"] == 0
        assert res["auto"] is True
        mock_send.assert_awaited_once_with("getInfraLedConfig")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.set_infra_led("auto")
        mock_send.assert_awaited_once_with("setInfraLedConfig", {"mode": "0"})

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.set_infra_led("on")
        assert mock_send.await_count == 2
        mock_send.assert_any_await("setInfraLedConfig", {"mode": "1"})
        mock_send.assert_any_await("openInfraLed")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.set_infra_led("off")
        assert mock_send.await_count == 2
        mock_send.assert_any_await("setInfraLedConfig", {"mode": "1"})
        mock_send.assert_any_await("closeInfraLed")


@pytest.mark.asyncio
async def test_volume_and_voice():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {"volume": "85"})
        assert await cam.get_volume() == 85
        mock_send.assert_awaited_once_with("getAudioVolume")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.set_volume(80)
        mock_send.assert_awaited_once_with("setAudioVolume", {"volume": "80"})

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {"isEnable": "1"})
        assert await cam.get_voice_state() is True
        mock_send.assert_awaited_once_with("getVoiceEnableState")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.set_voice_state(False)
        mock_send.assert_awaited_once_with("setVoiceEnableState", {"isEnable": "0"})


@pytest.mark.asyncio
async def test_white_light_and_siren():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.open_white_light()
        mock_send.assert_awaited_once_with("openWhiteLight")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.close_white_light()
        mock_send.assert_awaited_once_with("closeWhiteLight")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {"sirenEnable": "0", "sirenvolume": "100"})
        cfg = await cam.get_siren_config()
        assert cfg["sirenvolume"] == "100"
        mock_send.assert_awaited_once_with("getSirenConfig")

    with patch.object(cam, "_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (0, {})
        await cam.set_siren_config(True, volume=90)
        mock_send.assert_awaited_once_with("setSirenConfig", {
            "sirenEnable": "1",
            "sirenvolume": "90",
            "reserved": "0"
        })


@pytest.mark.asyncio
async def test_get_full_state():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    with patch.object(cam, "get_state", new_callable=AsyncMock) as mock_state,          patch.object(cam, "is_asleep", new_callable=AsyncMock) as mock_sleep,          patch.object(cam, "get_led_state", new_callable=AsyncMock) as mock_led,          patch.object(cam, "get_flip_and_mirror", new_callable=AsyncMock) as mock_mf,          patch.object(cam, "get_infra_led_config", new_callable=AsyncMock) as mock_ir,          patch.object(cam, "get_volume", new_callable=AsyncMock) as mock_vol,          patch.object(cam, "get_voice_state", new_callable=AsyncMock) as mock_voice,          patch.object(cam, "get_white_light_brightness", new_callable=AsyncMock) as mock_wl,          patch.object(cam, "get_siren_config", new_callable=AsyncMock) as mock_siren:

        mock_state.return_value = {"motion_detected": False, "is_recording": False}
        mock_sleep.return_value = False
        mock_led.return_value = True
        mock_mf.return_value = {"is_flip": False, "is_mirror": False}
        mock_ir.return_value = {"mode": 0, "auto": True}
        mock_vol.return_value = 100
        mock_voice.return_value = True
        mock_wl.side_effect = FoscamCommandError("Unsupported")
        mock_siren.side_effect = FoscamCommandError("Unsupported")

        full = await cam.get_full_state()
        assert full["motion_detected"] is False
        assert full["is_asleep"] is False
        assert full["led_enabled"] is True
        assert full["volume"] == 100
        assert full["white_light"] is None
        assert full["siren"] is None
