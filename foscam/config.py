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


def normalize_name(s: str) -> str:
    """Normalize camera name for flexible CLI matching."""
    return s.lower().replace("_", "-").replace(" ", "-").strip()


def find_hass_config_dir(hint_path: Path | str | None = None) -> Path | None:
    """Locate Home Assistant base configuration directory."""
    if hint_path and str(hint_path) != "__AUTO__":
        p = Path(hint_path).resolve()
        if p.is_file():
            return p.parent.parent if p.parent.name == ".storage" else p.parent
        if (p / ".storage" / "core.config_entries").is_file() or (p / ".storage" / "core.config.entries").is_file():
            return p
        if (p / "core.config_entries").is_file():
            return p
        if p.is_dir() and ((p / ".storage").is_dir() or str(p) != "/config"):
            return p

    candidates: list[Path] = []
    # Environment variables
    for env_var in ("HASS_DIR", "HASS_CONFIG", "HOMEASSISTANT_DIR"):
        if env_var in os.environ:
            candidates.append(Path(os.environ[env_var]))

    # Standard /config in HA container/OS
    candidates.append(Path("/config"))

    # Current working directory
    candidates.append(Path.cwd())

    # Standard ~/.homeassistant
    candidates.append(Path.home() / ".homeassistant")

    # Common site directories (~/ha/sites/*/home-assistant)
    sites_dir = Path.home() / "ha" / "sites"
    if sites_dir.is_dir():
        for site in sites_dir.iterdir():
            candidates.append(site / "home-assistant")

    for cand in candidates:
        if (cand / ".storage" / "core.config_entries").is_file() or (cand / ".storage" / "core.config.entries").is_file():
            return cand

    return None


def read_hass_config(hass_path: Path | str | None = None) -> dict[str, Any]:
    """Read Foscam cameras from Home Assistant core.config_entries."""
    base_dir = find_hass_config_dir(hass_path)
    if not base_dir:
        checked = str(hass_path) if hass_path else "/config, ~/.homeassistant, ~/ha/sites/*"
        raise FoscamConfigError(f"Home Assistant configuration directory not found (checked: {checked})")

    entries_file = None
    for cand in (
        base_dir / ".storage" / "core.config_entries",
        base_dir / ".storage" / "core.config.entries",
        base_dir / "core.config_entries",
    ):
        if cand.is_file():
            entries_file = cand
            break

    if not entries_file:
        raise FoscamConfigError(f"core.config_entries not found under {base_dir}")

    try:
        with open(entries_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as err:
        raise FoscamConfigError(f"Failed to read {entries_file}: {err}") from err

    entries = data.get("data", {}).get("entries", [])
    cameras: dict[str, Any] = {}
    default_cam = None

    for entry in entries:
        if not isinstance(entry, dict) or entry.get("domain") != "foscam":
            continue
        title = entry.get("title") or entry.get("entry_id", "foscam")
        entry_data = entry.get("data", {})

        cam_info = {
            "name": title,
            "host": entry_data.get("host"),
            "port": entry_data.get("port", DEFAULT_PORT),
            "rtsp_port": entry_data.get("rtsp_port", DEFAULT_RTSP_PORT),
            "username": entry_data.get("username", ""),
            "password": entry_data.get("password", ""),
            "stream": entry_data.get("stream", "Main"),
            "storage_dir": str(base_dir / "foscam"),
            "source": f"Home Assistant ({entries_file})",
        }
        cameras[title] = cam_info

        # Also register normalized alias (e.g. back-garden for Back_Garden)
        norm = normalize_name(title)
        if norm not in cameras:
            cameras[norm] = cam_info

        if default_cam is None:
            default_cam = title

    if not cameras:
        raise FoscamConfigError(f"No 'foscam' entries found in {entries_file}")

    return {
        "default": default_cam,
        "cameras": cameras,
        "storage_dir": str(base_dir / "foscam"),
        "source": str(base_dir),
    }


def load_config(
    config_path: Path | str | None = None,
    hass_path: Path | str | None = None,
) -> dict[str, Any]:
    """Load configuration from JSON file or Home Assistant."""
    if hass_path:
        return read_hass_config(hass_path)

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


def get_camera_config(
    name: str | None = None,
    config_path: Path | str | None = None,
    hass_path: Path | str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Get configuration for a named camera or the default camera.

    Returns tuple of (camera_name, camera_dict).
    """
    conf = load_config(config_path=config_path, hass_path=hass_path)
    cameras = conf.get("cameras", {})

    if not cameras:
        if hass_path:
            raise FoscamConfigError(f"No Foscam cameras found in Home Assistant ({hass_path}).")
        raise FoscamConfigError("No cameras configured. Use 'pyfoscam config add' first.")

    target_name = name
    if not target_name:
        target_name = conf.get("default")
        if not target_name and len(cameras) == 1:
            target_name = next(iter(cameras.keys()))

    if target_name and target_name not in cameras:
        # Try normalized lookup
        norm = normalize_name(target_name)
        if norm in cameras:
            target_name = norm

    if not target_name or target_name not in cameras:
        # Show unique camera names
        available = ", ".join(sorted({c.get("name", k) for k, c in cameras.items()}))
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
