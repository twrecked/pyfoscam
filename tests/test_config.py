"""Tests for pyfoscam configuration handling."""
import json
from pathlib import Path
import pytest

from foscam.config import (
    get_camera_config,
    load_config,
    normalize_name,
    read_hass_config,
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


def test_normalize_name():
    assert normalize_name("Back_Garden") == "back-garden"
    assert normalize_name("Front Porch Camera") == "front-porch-camera"
    assert normalize_name("Garage") == "garage"


def test_read_hass_config(tmp_path: Path):
    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir(parents=True)
    entries_file = storage_dir / "core.config_entries"

    mock_entries = {
        "version": 1,
        "data": {
            "entries": [
                {
                    "domain": "foscam",
                    "title": "Front_Yard",
                    "data": {
                        "host": "192.168.1.55",
                        "port": 88,
                        "rtsp_port": 554,
                        "username": "admin",
                        "password": "mypassword",
                    },
                },
                {
                    "domain": "other_integration",
                    "title": "Other",
                    "data": {},
                },
            ]
        },
    }
    entries_file.write_text(json.dumps(mock_entries), encoding="utf-8")

    conf = read_hass_config(tmp_path)
    assert conf["default"] == "Front_Yard"
    assert "Front_Yard" in conf["cameras"]
    assert "front-yard" in conf["cameras"]  # normalized alias
    assert conf["cameras"]["Front_Yard"]["host"] == "192.168.1.55"

    # Test get_camera_config via hass_path
    name, cam_cfg = get_camera_config("front-yard", hass_path=tmp_path)
    assert cam_cfg["host"] == "192.168.1.55"
    assert cam_cfg["username"] == "admin"

