"""Media objects and library management for Foscam recordings."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .exceptions import FoscamConnectionError, FoscamMediaError
from .transcode import convert_avi_to_mp4, get_video_duration, is_ffmpeg_available

if TYPE_CHECKING:
    from .client import FoscamCamera

LOGGER = logging.getLogger(__package__)


class FoscamRecording:
    """Represents a video recording on camera local storage."""

    def __init__(
        self,
        clip_id: str,
        created_at: datetime,
        remote_video: str,
        remote_thumbnail: str | None,
        remote_size: int,
        trigger: str = "motion",
        storage_dir: Path | str | None = None,
    ) -> None:
        self.clip_id = clip_id
        self.created_at = created_at
        self.remote_video = remote_video
        self.remote_thumbnail = remote_thumbnail
        self.remote_size = remote_size
        self.trigger = trigger

        self._storage_dir = Path(storage_dir) if storage_dir else Path.cwd() / "foscam"
        self._duration: int | None = None

    @property
    def local_video_path(self) -> Path:
        """Path to local MP4 video file."""
        return self._storage_dir / f"{self.clip_id}.mp4"

    @property
    def local_raw_path(self) -> Path:
        """Path to local raw AVI video file."""
        return self._storage_dir / f"{self.clip_id}.avi"

    @property
    def local_thumbnail_path(self) -> Path:
        """Path to local JPEG thumbnail file."""
        return self._storage_dir / f"{self.clip_id}.jpg"

    @property
    def content_url(self) -> str:
        """Return string path to local video file for HA compatibility."""
        return str(self.local_video_path)

    @property
    def thumbnail_url(self) -> str:
        """Return string path to local thumbnail file for HA compatibility."""
        return str(self.local_thumbnail_path)

    @property
    def content_type(self) -> str:
        return "video/mp4"

    @property
    def thumbnail_type(self) -> str:
        return "image/jpeg"

    @property
    def object_type(self) -> str | None:
        return self.trigger

    @property
    def object_region(self) -> None:
        return None

    @property
    def is_downloaded(self) -> bool:
        """Check if local MP4 file exists and has size."""
        p = self.local_video_path
        return p.is_file() and p.stat().st_size > 0

    @property
    def is_raw_downloaded(self) -> bool:
        """Check if local AVI file exists and has size."""
        p = self.local_raw_path
        return p.is_file() and p.stat().st_size > 0

    @property
    def is_thumbnail_downloaded(self) -> bool:
        """Check if local thumbnail file exists."""
        p = self.local_thumbnail_path
        return p.is_file() and p.stat().st_size > 0

    @property
    def duration(self) -> int:
        """Duration in seconds (defaults to cached probed duration or 1)."""
        return self._duration if self._duration is not None else 1

    async def async_get_duration(self) -> int:
        """Probe video duration asynchronously if not already cached."""
        if self._duration is None:
            if self.is_downloaded:
                self._duration = await get_video_duration(self.local_video_path)
            elif self.is_raw_downloaded:
                self._duration = await get_video_duration(self.local_raw_path)
        return self._duration if self._duration is not None else 1

    def created_at_pretty(self, date_format: str = "%m-%d %H:%M:%S") -> str:
        """Return formatted date string."""
        return self.created_at.strftime(date_format)

    def to_dict(self) -> dict[str, Any]:
        """Convert recording to dictionary metadata."""
        return {
            "clip_id": self.clip_id,
            "created_at": self.created_at.isoformat(),
            "created_at_pretty": self.created_at_pretty(),
            "trigger": self.trigger,
            "remote_video": self.remote_video,
            "remote_thumbnail": self.remote_thumbnail,
            "remote_size": self.remote_size,
            "duration": self.duration,
            "is_downloaded": self.is_downloaded,
            "local_video_path": str(self.local_video_path) if self.is_downloaded else None,
            "local_thumbnail_path": str(self.local_thumbnail_path)
            if self.is_thumbnail_downloaded
            else None,
        }

    def __repr__(self) -> str:
        return f"<FoscamRecording {self.clip_id} ({self.created_at}) {self.remote_size}B>"


class FoscamMediaLibrary:
    """Manages recordings and media access for a Foscam camera asynchronously."""

    def __init__(
        self,
        camera: FoscamCamera,
        storage_dir: Path | str | None = None,
        days_cutoff: int = 15,
    ) -> None:
        self.camera = camera
        self.storage_dir = Path(storage_dir) if storage_dir else Path.cwd() / "foscam"
        self.days_cutoff = days_cutoff

        self._recordings: list[FoscamRecording] = []
        self._bad_recordings: set[str] = set()
        self._last_refresh: datetime | None = None

    @property
    def cache_path(self) -> Path:
        """Return camera-specific cache file path."""
        safe_id = re.sub(r"[^0-9a-zA-Z]+", "_", self.camera.host)
        return self.storage_dir / f".cache_{safe_id}.json"

    def _load_cache_sync(self, cutoff_date: datetime) -> dict[str, list[dict[str, Any]]]:
        """Load and prune historical cached records from disk (synchronous)."""
        cache_file = self.cache_path
        if not cache_file.is_file():
            return {}

        try:
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
            days: dict[str, list[dict[str, Any]]] = data.get("days", {})

            # Prune dates older than cutoff_date
            cutoff_day = cutoff_date.strftime("%Y%m%d")
            pruned_days = {
                day: records for day, records in days.items() if day >= cutoff_day
            }
            return pruned_days
        except (json.JSONDecodeError, OSError) as err:
            LOGGER.debug("Could not read media cache %s: %s", cache_file, err)
            return {}

    def _save_cache_sync(self, days_data: dict[str, list[dict[str, Any]]]) -> None:
        """Atomically save cached records to disk (synchronous)."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_path
        temp_file = self.storage_dir / f"{cache_file.name}.tmp"

        payload = {
            "version": 1,
            "camera": self.camera.host,
            "last_updated": datetime.now().isoformat(),
            "days": days_data,
        }
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(temp_file, cache_file)
        except OSError as err:
            LOGGER.warning("Failed writing media cache to %s: %s", cache_file, err)
            if temp_file.is_file():
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass

    async def clear_cache(self) -> None:
        """Clear cache file on disk and reset in-memory recordings."""
        def _clear() -> None:
            if self.cache_path.is_file():
                try:
                    os.unlink(self.cache_path)
                except OSError as err:
                    LOGGER.debug("Failed deleting cache %s: %s", self.cache_path, err)

        await asyncio.to_thread(_clear)
        self._recordings = []
        self._last_refresh = None

    @property
    def recordings(self) -> list[FoscamRecording]:
        """List of all discovered recordings, newest first."""
        return self._recordings

    @property
    def captured_today(self) -> int:
        """Number of clips recorded today."""
        today = datetime.now().date()
        return sum(1 for r in self._recordings if r.created_at.date() == today)

    @property
    def captured_total(self) -> int:
        """Total number of recordings in library."""
        return len(self._recordings)

    @property
    def last_capture_at(self) -> datetime | None:
        """Timestamp of most recent recording."""
        if not self._recordings:
            return None
        return self._recordings[0].created_at

    def get_recording(self, clip_id: str) -> FoscamRecording | None:
        """Look up recording by clip ID."""
        for r in self._recordings:
            if r.clip_id == clip_id:
                return r
        return None

    async def refresh(
        self, mac: str | None = None, force: bool = False
    ) -> list[FoscamRecording]:
        """Scan camera FTP for recordings with historical date caching."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        today_str = now.strftime("%Y%m%d")
        cutoff_date = now - timedelta(days=self.days_cutoff)

        if force:
            cached_days: dict[str, list[dict[str, Any]]] = {}
            skip_dates: set[str] = set()
        else:
            cached_days = await asyncio.to_thread(self._load_cache_sync, cutoff_date)
            # Only skip dates strictly prior to today that are already cached
            skip_dates = set(cached_days.keys()) - {today_str}

        await self.camera.start_ftp_server()
        ftp_client = self.camera.get_ftp_client()

        async with ftp_client:
            _, raw_records = await ftp_client.list_media(
                mac,
                since_date=cutoff_date.date(),
                skip_dates=skip_dates,
            )

        # Partition freshly discovered records by day
        new_days: dict[str, list[dict[str, Any]]] = {}
        for r in raw_records:
            dt: datetime = r["date"]
            d_str = dt.strftime("%Y%m%d")
            new_days.setdefault(d_str, []).append(
                {
                    "clip_id": r["clip_id"],
                    "filename": r["filename"],
                    "date": dt.isoformat(),
                    "trigger": r["trigger"],
                    "remote_video": r["remote_video"],
                    "remote_snapshot": r["remote_snapshot"],
                    "size": r["size"],
                }
            )

        # Replace today with fresh records, and add any previously un-cached days
        for d_str, records in new_days.items():
            cached_days[d_str] = records

        # If today had 0 recordings from camera, ensure today is updated as empty
        if today_str not in new_days:
            cached_days[today_str] = []

        # Persist updated cache to disk
        await asyncio.to_thread(self._save_cache_sync, cached_days)

        # Reconstruct FoscamRecording objects from all cached days
        recordings: list[FoscamRecording] = []
        for records in cached_days.values():
            for r in records:
                clip_id = r["clip_id"]
                if clip_id in self._bad_recordings:
                    continue

                raw_dt = r["date"]
                dt = (
                    datetime.fromisoformat(raw_dt)
                    if isinstance(raw_dt, str)
                    else raw_dt
                )
                if dt < cutoff_date:
                    continue

                rec = FoscamRecording(
                    clip_id=clip_id,
                    created_at=dt,
                    remote_video=r["remote_video"],
                    remote_thumbnail=r["remote_snapshot"],
                    remote_size=r["size"],
                    trigger=r["trigger"],
                    storage_dir=self.storage_dir,
                )
                recordings.append(rec)

        self._recordings = sorted(recordings, key=lambda x: x.created_at, reverse=True)
        self._last_refresh = datetime.now()
        return self._recordings

    async def download_recording(
        self,
        recording_or_clip_id: FoscamRecording | str,
        dest_video: Path | str | None = None,
        dest_thumbnail: Path | str | None = None,
        remux_to_mp4: bool = True,
        force: bool = False,
    ) -> tuple[Path, Path | None]:
        """Download a recording and optional thumbnail asynchronously.

        Returns (video_path, thumbnail_path).
        """
        if isinstance(recording_or_clip_id, str):
            rec = self.get_recording(recording_or_clip_id)
            if not rec:
                raise FoscamMediaError(f"Recording '{recording_or_clip_id}' not found in library")
        else:
            rec = recording_or_clip_id

        self.storage_dir.mkdir(parents=True, exist_ok=True)

        target_video = (
            Path(dest_video)
            if dest_video
            else (rec.local_video_path if remux_to_mp4 else rec.local_raw_path)
        )
        target_thumbnail = (
            Path(dest_thumbnail) if dest_thumbnail else rec.local_thumbnail_path
        )

        # If already downloaded and not forcing
        if not force and target_video.is_file() and target_video.stat().st_size > 0:
            return target_video, (target_thumbnail if target_thumbnail.is_file() else None)

        await self.camera.start_ftp_server()
        ftp_client = self.camera.get_ftp_client()

        async with ftp_client:
            # 1. Download thumbnail if available
            if rec.remote_thumbnail:
                try:
                    await ftp_client.download_file(rec.remote_thumbnail, str(target_thumbnail))
                except (FoscamMediaError, FoscamConnectionError, OSError) as err:
                    LOGGER.debug("Thumbnail download failed for %s: %s", rec.clip_id, err)

            # 2. Download video
            if not remux_to_mp4 or not is_ffmpeg_available():
                await ftp_client.download_file(rec.remote_video, str(target_video))
                rec._duration = await get_video_duration(target_video)
                return target_video, (target_thumbnail if target_thumbnail.is_file() else None)

            # Download AVI to temporary file and remux
            with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as tmp_avi:
                tmp_avi_path = tmp_avi.name

            try:
                await ftp_client.download_file(rec.remote_video, tmp_avi_path)
                await convert_avi_to_mp4(tmp_avi_path, target_video)
                rec._duration = await get_video_duration(target_video)
            except Exception as err:
                self._bad_recordings.add(rec.clip_id)
                if os.path.exists(target_video):
                    try:
                        os.unlink(target_video)
                    except OSError:
                        pass
                raise FoscamMediaError(f"Failed processing recording {rec.clip_id}: {err}") from err
            finally:
                if os.path.exists(tmp_avi_path):
                    try:
                        os.unlink(tmp_avi_path)
                    except OSError:
                        pass

        return target_video, (target_thumbnail if target_thumbnail.is_file() else None)
