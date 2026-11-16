"""Configuration management for pyfoscam."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import platformdirs

from .const import DEFAULT_PORT, DEFAULT_RTSP_PORT
from .exceptions import FoscamConfigError

APP_NAME = "pyfoscam"


def get_config_dir() -> Path:
    """Return OS config directory for foscam."""
    return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False))


def get_default_config_path() -> Path:
    """Return default config file path."""
    return get_config_dir() / "cameras.json"


def load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load configuration from JSON file."""
    path = Path(config_path) if config_path is not None else get_default_config_path()
    if not path.is_file():
        return {"default": None, "cameras": {}}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"default": None, "cameras": {}}
            data.setdefault("cameras", {})
            return data
    except Exception as err:
        raise FoscamConfigError(f"Failed to read config from {path}: {err}") from err


def save_config(config_data: dict[str, Any], config_path: Path | str | None = None) -> None:
    """Save configuration to JSON file."""
    path = Path(config_path) if config_path is not None else get_default_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
    except Exception as err:
        raise FoscamConfigError(f"Failed to save config to {path}: {err}") from err


def get_camera_config(name: str | None = None, config_path: Path | str | None = None) -> tuple[str, dict[str, Any]]:
    """Get configuration for a named camera or the default camera.

    Returns tuple of (camera_name, camera_dict).
    """
    conf = load_config(config_path)
    cameras = conf.get("cameras", {})

    if not cameras:
        raise FoscamConfigError("No cameras configured. Use 'pyfoscam config add' first.")

    target_name = name
    if not target_name:
        target_name = conf.get("default")
        if not target_name and len(cameras) == 1:
            target_name = next(iter(cameras.keys()))

    if not target_name or target_name not in cameras:
        available = ", ".join(cameras.keys())
        raise FoscamConfigError(f"Camera '{name or 'default'}' not found. Available: {available}")

    return target_name, cameras[target_name]


def set_camera_config(
    name: str,
    host: str,
    username: str,
    password: str,
    port: int = DEFAULT_PORT,
    rtsp_port: int = DEFAULT_RTSP_PORT,
    is_default: bool = False,
    config_path: Path | str | None = None,
) -> None:
    """Add or update a camera configuration."""
    conf = load_config(config_path)
    cameras = conf.setdefault("cameras", {})

    cameras[name] = {
        "host": host,
        "port": int(port),
        "rtsp_port": int(rtsp_port),
        "username": username,
        "password": password,
    }

    if is_default or not conf.get("default") or len(cameras) == 1:
        conf["default"] = name

    save_config(conf, config_path)


def remove_camera_config(name: str, config_path: Path | str | None = None) -> bool:
    """Remove a camera from configuration."""
    conf = load_config(config_path)
    cameras = conf.get("cameras", {})

    if name not in cameras:
        return False

    del cameras[name]
    if conf.get("default") == name:
        conf["default"] = next(iter(cameras.keys())) if cameras else None

    save_config(conf, config_path)
    return True
