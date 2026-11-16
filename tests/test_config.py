"""Tests for pyfoscam configuration handling."""
from pathlib import Path
import pytest

from foscam.config import (
    get_camera_config,
    load_config,
    remove_camera_config,
    save_config,
    set_camera_config,
)
from foscam.exceptions import FoscamConfigError


def test_empty_config(tmp_path: Path):
    cfg_file = tmp_path / "cameras.json"
    conf = load_config(cfg_file)
    assert conf == {"default": None, "cameras": {}}


def test_add_and_get_camera(tmp_path: Path):
    cfg_file = tmp_path / "cameras.json"
    set_camera_config(
        name="driveway",
        host="192.168.1.100",
        username="admin",
        password="secretpassword",
        port=88,
        rtsp_port=554,
        config_path=cfg_file,
    )

    cam_name, cam_cfg = get_camera_config("driveway", cfg_file)
    assert cam_name == "driveway"
    assert cam_cfg["host"] == "192.168.1.100"
    assert cam_cfg["username"] == "admin"
    assert cam_cfg["password"] == "secretpassword"

    # Default should automatically be driveway
    cam_name_def, cam_cfg_def = get_camera_config(None, cfg_file)
    assert cam_name_def == "driveway"
    assert cam_cfg_def["host"] == "192.168.1.100"


def test_multiple_cameras_and_default(tmp_path: Path):
    cfg_file = tmp_path / "cameras.json"
    set_camera_config("cam1", "10.0.0.1", "user1", "pass1", config_path=cfg_file)
    set_camera_config("cam2", "10.0.0.2", "user2", "pass2", is_default=True, config_path=cfg_file)

    conf = load_config(cfg_file)
    assert conf["default"] == "cam2"
    assert len(conf["cameras"]) == 2

    cam_name, _ = get_camera_config(None, cfg_file)
    assert cam_name == "cam2"

    # Remove cam2
    assert remove_camera_config("cam2", cfg_file) is True
    conf_after = load_config(cfg_file)
    assert "cam2" not in conf_after["cameras"]
    assert conf_after["default"] == "cam1"


def test_nonexistent_camera(tmp_path: Path):
    cfg_file = tmp_path / "cameras.json"
    set_camera_config("cam1", "10.0.0.1", "user1", "pass1", config_path=cfg_file)
    with pytest.raises(FoscamConfigError, match="Camera 'missing' not found"):
        get_camera_config("missing", cfg_file)
