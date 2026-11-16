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
