"""FTP client for Foscam local storage access."""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any

from ftpretty import ftpretty

from .const import DEFAULT_FTP_PORT
from .exceptions import FoscamConnectionError

LOGGER = logging.getLogger(__package__)

TIMESTAMP_PATTERN = re.compile(r"(\d{8})[-_](\d{6})")


def parse_timestamp_from_filename(filename: str) -> datetime | None:
    """Extract datetime from Foscam filename.

    Examples:
        MD20210522_120400.avi -> 2021-05-22 12:04:00
        Schedule20210522-120400.avi -> 2021-05-22 12:04:00
        snap_20210522_120400.jpg -> 2021-05-22 12:04:00
    """
    base = os.path.splitext(os.path.basename(filename))[0]
    match = TIMESTAMP_PATTERN.search(base)
    if not match:
        return None
    date_str, time_str = match.groups()
    try:
        return datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def parse_trigger_from_filename(filename: str) -> str:
    """Infer trigger type from filename."""
    base = os.path.basename(filename).lower()
    if base.startswith("md") or "motion" in base:
        return "motion"
    if base.startswith("sched"):
        return "schedule"
    if base.startswith("manual"):
        return "manual"
    if base.startswith("alarm"):
        return "alarm"
    return "unknown"


class FoscamFTPClient:
    """Interacts with Foscam camera FTP server."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = DEFAULT_FTP_PORT,
        timeout: int = 15,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self._ftp: ftpretty | None = None

    def connect(self) -> ftpretty:
        """Connect to FTP server."""
        if self._ftp is not None:
            return self._ftp
        try:
            self._ftp = ftpretty(
                self.host,
                self.username,
                self.password,
                port=self.port,
                timeout=self.timeout,
            )
            return self._ftp
        except Exception as err:
            raise FoscamConnectionError(f"FTP connection to {self.host}:{self.port} failed: {err}") from err

    def close(self) -> None:
        """Close FTP connection."""
        if self._ftp is not None:
            try:
                self._ftp.close()
            except Exception:
                pass
            self._ftp = None

    def __enter__(self) -> FoscamFTPClient:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def discover_camera_dir(self, mac: str | None = None) -> str:
        """Find the root IPCamera folder for this camera MAC or the first camera found."""
        ftp = self.connect()
        try:
            dirs = ftp.list("/IPCamera")
        except Exception as err:
            raise FoscamConnectionError(f"Failed to list /IPCamera: {err}") from err

        clean_mac = mac.replace(":", "").replace("-", "").upper() if mac else None

        for d in dirs:
            dir_name = os.path.basename(d)
            if clean_mac and clean_mac in dir_name.upper():
                return f"/IPCamera/{dir_name}"

        # If mac wasn't specified or didn't match directly, take the first valid folder
        if dirs:
            first = os.path.basename(dirs[0])
            return f"/IPCamera/{first}"

        raise FoscamConnectionError("No camera directories found under /IPCamera")

    def list_media(self, mac: str | None = None) -> tuple[dict[datetime, str], list[dict[str, Any]]]:
        """Scan FTP directory for snapshots and recordings.

        Returns:
            (snapshots_dict {datetime: remote_path}, recordings_list [dict])
        """
        ftp = self.connect()
        cam_dir = self.discover_camera_dir(mac)

        snapshots: dict[datetime, str] = {}
        recordings: list[dict[str, Any]] = []

        # 1. Discover snapshots
        snap_root = f"{cam_dir}/snap"
        try:
            for date1 in ftp.list(snap_root):
                d1_path = f"{snap_root}/{os.path.basename(date1)}"
                try:
                    for date2 in ftp.list(d1_path):
                        d2_path = f"{d1_path}/{os.path.basename(date2)}"
                        try:
                            for snap in ftp.list(d2_path, extra=True):
                                fname = snap.get("name", "")
                                if not fname.lower().endswith((".jpg", ".jpeg")):
                                    continue
                                full_path = f"{d2_path}/{fname}"
                                dt = parse_timestamp_from_filename(fname)
                                if dt:
                                    snapshots[dt] = full_path
                        except Exception as err:
                            LOGGER.debug("Error listing snaps in %s: %s", d2_path, err)
                except Exception as err:
                    LOGGER.debug("Error listing date2 in %s: %s", d1_path, err)
        except Exception as err:
            LOGGER.debug("Error listing %s: %s", snap_root, err)

        # 2. Discover recordings
        record_root = f"{cam_dir}/record"
        try:
            for date1 in ftp.list(record_root):
                d1_path = f"{record_root}/{os.path.basename(date1)}"
                try:
                    for date2 in ftp.list(d1_path):
                        d2_path = f"{d1_path}/{os.path.basename(date2)}"
                        try:
                            for rec in ftp.list(d2_path, extra=True):
                                fname = rec.get("name", "")
                                if not fname.lower().endswith(".avi"):
                                    continue
                                full_path = f"{d2_path}/{fname}"
                                dt = parse_timestamp_from_filename(fname)
                                if not dt:
                                    continue

                                # Match closest thumbnail
                                snap_path = None
                                matching_snaps = [k for k in sorted(snapshots.keys()) if k >= dt]
                                if matching_snaps:
                                    snap_path = snapshots[matching_snaps[0]]
                                elif snapshots:
                                    # Fallback to latest available snapshot before recording
                                    snap_path = snapshots[sorted(snapshots.keys())[-1]]

                                trigger = parse_trigger_from_filename(fname)
                                base_id = os.path.splitext(fname)[0]

                                recordings.append({
                                    "clip_id": base_id,
                                    "filename": fname,
                                    "date": dt,
                                    "trigger": trigger,
                                    "remote_video": full_path,
                                    "remote_snapshot": snap_path,
                                    "size": int(rec.get("size", 0)),
                                })
                        except Exception as err:
                            LOGGER.debug("Error listing recordings in %s: %s", d2_path, err)
                except Exception as err:
                    LOGGER.debug("Error listing date2 in %s: %s", d1_path, err)
        except Exception as err:
            LOGGER.debug("Error listing %s: %s", record_root, err)

        return snapshots, recordings

    def download_file(self, remote_path: str, local_path: str) -> None:
        """Download remote file via FTP."""
        ftp = self.connect()
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        try:
            ftp.get(remote_path, local_path)
        except Exception as err:
            raise FoscamConnectionError(f"FTP get {remote_path} -> {local_path} failed: {err}") from err
