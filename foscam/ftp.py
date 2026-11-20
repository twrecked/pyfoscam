"""FTP client for Foscam local storage access."""
from __future__ import annotations

import asyncio
import ftplib
import logging
import os
import re
import time
import types
from datetime import date, datetime
from typing import Any, Self

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
    """Interacts with Foscam camera FTP server asynchronously."""

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
        self._lock = asyncio.Lock()

    def _connect_sync(self, retries: int = 5, retry_interval: float = 0.5) -> ftpretty:
        """Connect to FTP server with retry for daemon startup (synchronous)."""
        if self._ftp is not None:
            return self._ftp

        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                self._ftp = ftpretty(
                    self.host,
                    self.username,
                    self.password,
                    port=self.port,
                    timeout=self.timeout,
                )
                return self._ftp
            except (ConnectionRefusedError, OSError) as err:
                last_err = err
                if attempt < retries - 1:
                    LOGGER.debug(
                        "FTP connect failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        retries,
                        retry_interval,
                        err,
                    )
                    time.sleep(retry_interval)
                else:
                    raise FoscamConnectionError(
                        f"FTP connection to {self.host}:{self.port} failed after {retries} attempts: {err}"
                    ) from err
            except Exception as err:
                raise FoscamConnectionError(
                    f"FTP connection to {self.host}:{self.port} failed: {err}"
                ) from err

        if last_err:
            raise FoscamConnectionError(
                f"FTP connection to {self.host}:{self.port} failed: {last_err}"
            ) from last_err
        raise FoscamConnectionError(f"FTP connection to {self.host}:{self.port} failed")

    def _close_sync(self) -> None:
        """Close FTP connection (synchronous)."""
        if self._ftp is not None:
            try:
                self._ftp.close()
            except (ftplib.Error, OSError) as err:
                LOGGER.debug("Error closing FTP connection: %s", err)
            self._ftp = None

    def _discover_camera_dir_sync(self, mac: str | None = None) -> str:
        """Find the root IPCamera folder for this camera MAC (synchronous)."""
        ftp = self._connect_sync()
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

    def _list_media_sync(
        self,
        mac: str | None = None,
        since_date: datetime | date | None = None,
        skip_dates: set[str] | None = None,
    ) -> tuple[dict[datetime, str], list[dict[str, Any]]]:
        """Scan FTP directory for snapshots and recordings (synchronous)."""
        ftp = self._connect_sync()
        cam_dir = self._discover_camera_dir_sync(mac)

        since_str: str | None = None
        if since_date:
            since_str = since_date.strftime("%Y%m%d")

        skip_set = skip_dates or set()
        today_str = datetime.now().strftime("%Y%m%d")

        snapshots: dict[datetime, str] = {}
        recordings: list[dict[str, Any]] = []

        # 1. Discover snapshots
        snap_root = f"{cam_dir}/snap"
        try:
            for date1 in ftp.list(snap_root):
                d1_name = os.path.basename(date1)
                if since_str and d1_name < since_str:
                    continue
                if d1_name in skip_set and d1_name != today_str:
                    LOGGER.debug("Skipping cached snap date folder: %s", d1_name)
                    continue
                d1_path = f"{snap_root}/{d1_name}"
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
                        except (ftplib.Error, OSError) as err:
                            LOGGER.debug("Error listing snaps in %s: %s", d2_path, err)
                except (ftplib.Error, OSError) as err:
                    LOGGER.debug("Error listing date2 in %s: %s", d1_path, err)
        except (ftplib.Error, OSError) as err:
            LOGGER.debug("Error listing %s: %s", snap_root, err)

        # 2. Discover recordings
        record_root = f"{cam_dir}/record"
        try:
            for date1 in ftp.list(record_root):
                d1_name = os.path.basename(date1)
                if since_str and d1_name < since_str:
                    continue
                if d1_name in skip_set and d1_name != today_str:
                    LOGGER.debug("Skipping cached recording date folder: %s", d1_name)
                    continue
                d1_path = f"{record_root}/{d1_name}"
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
                                    snap_path = snapshots[max(snapshots.keys())]

                                trigger = parse_trigger_from_filename(fname)
                                base_id = os.path.splitext(fname)[0]

                                recordings.append(
                                    {
                                        "clip_id": base_id,
                                        "filename": fname,
                                        "date": dt,
                                        "trigger": trigger,
                                        "remote_video": full_path,
                                        "remote_snapshot": snap_path,
                                        "size": int(rec.get("size", 0)),
                                    }
                                )
                        except (ftplib.Error, OSError) as err:
                            LOGGER.debug("Error listing recordings in %s: %s", d2_path, err)
                except (ftplib.Error, OSError) as err:
                    LOGGER.debug("Error listing date2 in %s: %s", d1_path, err)
        except (ftplib.Error, OSError) as err:
            LOGGER.debug("Error listing %s: %s", record_root, err)

        return snapshots, recordings

    def _download_file_sync(self, remote_path: str, local_path: str) -> None:
        """Download remote file via FTP (synchronous)."""
        ftp = self._connect_sync()
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        try:
            ftp.get(remote_path, local_path)
        except Exception as err:
            raise FoscamConnectionError(
                f"FTP get {remote_path} -> {local_path} failed: {err}"
            ) from err

    async def connect(self, retries: int = 5, retry_interval: float = 0.5) -> None:
        """Connect to FTP server asynchronously."""
        async with self._lock:
            await asyncio.to_thread(self._connect_sync, retries, retry_interval)

    async def close(self) -> None:
        """Close FTP connection asynchronously."""
        async with self._lock:
            await asyncio.to_thread(self._close_sync)

    async def discover_camera_dir(self, mac: str | None = None) -> str:
        """Find root camera directory asynchronously."""
        async with self._lock:
            return await asyncio.to_thread(self._discover_camera_dir_sync, mac)

    async def list_media(
        self,
        mac: str | None = None,
        since_date: datetime | date | None = None,
        skip_dates: set[str] | None = None,
    ) -> tuple[dict[datetime, str], list[dict[str, Any]]]:
        """Scan FTP directory for snapshots and recordings asynchronously."""
        async with self._lock:
            return await asyncio.to_thread(self._list_media_sync, mac, since_date, skip_dates)

    async def download_file(self, remote_path: str, local_path: str) -> None:
        """Download remote file via FTP asynchronously."""
        async with self._lock:
            await asyncio.to_thread(self._download_file_sync, remote_path, local_path)

    def _file_size_sync(self, remote_path: str) -> int:
        """Read the current size using the same listing as the media catalog."""
        ftp = self._connect_sync()
        directory, filename = os.path.split(remote_path)
        try:
            for entry in ftp.list(directory, extra=True):
                if entry.get("name") == filename:
                    return int(entry["size"])
        except (ftplib.Error, OSError, KeyError, ValueError, TypeError) as err:
            raise FoscamConnectionError(f"Cannot read size of {remote_path}: {err}") from err
        raise FoscamConnectionError(f"Recording not found on camera: {remote_path}")

    async def file_size(self, remote_path: str) -> int:
        """Read a fresh byte count for a single remote file."""
        async with self._lock:
            return await asyncio.to_thread(self._file_size_sync, remote_path)

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        await self.close()
