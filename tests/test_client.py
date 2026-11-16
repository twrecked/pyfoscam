"""Tests for high-level FoscamCamera client."""
from unittest.mock import MagicMock, patch
import pytest

from foscam.client import FoscamCamera
from foscam.exceptions import FoscamAuthError, FoscamCommandError, FoscamConnectionError


def test_rtsp_url():
    cam = FoscamCamera("192.168.1.50", "admin", "secret", port=88, rtsp_port=554)
    assert cam.rtsp_url("Main") == "rtsp://admin:secret@192.168.1.50:554/videoMain"
    assert cam.rtsp_url("Sub") == "rtsp://admin:secret@192.168.1.50:554/videoSub"


def test_get_state():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    mock_raw_state = {
        "motionDetectAlarm": "2",
        "soundAlarm": "0",
        "IOAlarm": "0",
        "recording": "1",
    }
    with patch.object(cam._raw_cam, "get_dev_state", return_value=(0, mock_raw_state)):
        state = cam.get_state()
        assert state["motion_detected"] is True
        assert state["motion_enabled"] is True
        assert state["sound_detected"] is False
        assert state["sound_enabled"] is False
        assert state["is_recording"] is True


def test_error_handling():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")

    # Connection error (-1)
    with patch.object(cam._raw_cam, "get_dev_info", return_value=(-1, None)):
        with pytest.raises(FoscamConnectionError):
            cam.get_info()

    # Auth error (-2)
    with patch.object(cam._raw_cam, "get_dev_info", return_value=(-2, None)):
        with pytest.raises(FoscamAuthError):
            cam.get_info()

    # Command error (other non-zero)
    with patch.object(cam._raw_cam, "get_dev_info", return_value=(100, None)):
        with pytest.raises(FoscamCommandError):
            cam.get_info()


def test_ptz():
    cam = FoscamCamera("192.168.1.50", "admin", "secret")
    with patch.object(cam._raw_cam, "ptz_move_up", return_value=(0, {})) as mock_move, \
         patch.object(cam._raw_cam, "ptz_stop_run", return_value=(0, {})) as mock_stop, \
         patch("time.sleep"):
        cam.ptz("up", travel_time=0.1)
        mock_move.assert_called_once()
        mock_stop.assert_called_once()

    # Invalid movement
    with pytest.raises(FoscamCommandError, match="Invalid movement 'teleport'"):
        cam.ptz("teleport")
