"""Media objects and library management for Foscam recordings."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .exceptions import FoscamConnectionError, FoscamMediaError
from .ftp import parse_timestamp_from_filename
from .transcode import (
    convert_avi_to_mp4,
    get_video_duration,
    has_video_packets,
    is_ffmpeg_available,
    is_ffprobe_available,
)

if TYPE_CHECKING:
    from .client import FoscamCamera

LOGGER = logging.getLogger(__package__)
RECORDING_SETTLE_SECONDS = 10
# Old versions accepted header-only MP4s (observed at 262 bytes).
MIN_CACHED_MP4_BYTES = 512


@asynccontextmanager
async def _staging_directory(parent: Path) -> AsyncIterator[Path]:
    """Create and clean up a staging directory off the event loop."""
    creation = asyncio.create_task(
        asyncio.to_thread(tempfile.TemporaryDirectory, prefix=".foscam-", dir=parent)
    )
    try:
        directory = await asyncio.shield(creation)
    except asyncio.CancelledError:
        # The worker can still create the directory after cancellation.
        directory = await creation
        await asyncio.to_thread(directory.cleanup)
        raise
    try:
        yield Path(directory.name)
    finally:
        await asyncio.to_thread(directory.cleanup)


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except FileNotFoundError:
        return 0


def prune_local_recordings(
    storage_dir: Path | str,
    days: int = 30,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Prune local media files (.mp4, .avi, .jpg) older than specified days.

    Args:
        storage_dir: Directory containing downloaded recordings.
        days: Retention threshold in days; files older are deleted.
        dry_run: If True, calculate what would be deleted without deleting.

    Returns:
        (files_deleted_count, bytes_freed_total)
    """
    path = Path(storage_dir)
    if not path.is_dir():
        return 0, 0

    cutoff = datetime.now() - timedelta(days=days)
    deleted_count = 0
    bytes_freed = 0

    valid_extensions = {".mp4", ".avi", ".jpg", ".jpeg"}

    for entry in path.iterdir():
        if not entry.is_file() or entry.suffix.lower() not in valid_extensions:
            continue

        # Ignore hidden files like .cache_...json or .tmp files
        if entry.name.startswith("."):
            continue

        # Determine creation timestamp
        dt = parse_timestamp_from_filename(entry.name)
        if dt is None:
            # Fall back to file modification time
            try:
                dt = datetime.fromtimestamp(entry.stat().st_mtime)
            except OSError:
                continue

        if dt < cutoff:
            try:
                size = entry.stat().st_size
                if not dry_run:
                    entry.unlink(missing_ok=True)
                deleted_count += 1
                bytes_freed += size
            except OSError as err:
                LOGGER.debug("Failed deleting expired file %s: %s", entry, err)

    return deleted_count, bytes_freed


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
        """Check for a cached MP4, ignoring legacy header-only files."""
        return _file_size(self.local_video_path) >= MIN_CACHED_MP4_BYTES

    @property
    def is_raw_downloaded(self) -> bool:
        """Check if local AVI file exists and has size."""
        size = _file_size(self.local_raw_path)
        return size > 0 and (self.remote_size <= 0 or size == self.remote_size)

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
        self._download_lock = asyncio.Lock()
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

    async def prune_local(
        self, days: int | None = None, dry_run: bool = False
    ) -> tuple[int, int]:
        """Prune local downloaded recordings older than retention days."""
        retention = days if days is not None else self.days_cutoff
        return await asyncio.to_thread(
            prune_local_recordings, self.storage_dir, retention, dry_run
        )

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

        convert = remux_to_mp4 and is_ffmpeg_available()
        target_video = (
            Path(dest_video)
            if dest_video
            else (rec.local_video_path if convert else rec.local_raw_path)
        )
        target_thumbnail = (
            Path(dest_thumbnail) if dest_thumbnail else rec.local_thumbnail_path
        )

        async with self._download_lock:
            size = await asyncio.to_thread(_file_size, target_video)
            cached = (
                size >= MIN_CACHED_MP4_BYTES if convert else size > 0 and size == rec.remote_size
            )
            if cached and not force:
                return target_video, (target_thumbnail if target_thumbnail.is_file() else None)

            if convert and not is_ffprobe_available():
                raise FoscamMediaError("ffprobe is required to validate converted recordings")

            await asyncio.to_thread(target_video.parent.mkdir, parents=True, exist_ok=True)
            # Stage on the destination filesystem so publication is atomic.
            async with _staging_directory(target_video.parent) as staging:
                raw_video = staging / "recording.avi"
                await self.camera.start_ftp_server()
                async with self.camera.get_ftp_client() as ftp_client:
                    first_size = await ftp_client.file_size(rec.remote_video)
                    if first_size <= 0:
                        raise FoscamMediaError(f"Recording {rec.clip_id} is empty; retry later")
                    await asyncio.sleep(RECORDING_SETTLE_SECONDS)
                    expected_size = await ftp_client.file_size(rec.remote_video)
                    if expected_size != first_size:
                        raise FoscamMediaError(f"Recording {rec.clip_id} is still growing; retry later")

                    await ftp_client.download_file(rec.remote_video, str(raw_video))
                    received_size = await asyncio.to_thread(_file_size, raw_video)
                    final_size = await ftp_client.file_size(rec.remote_video)
                    if received_size != expected_size or final_size != expected_size:
                        raise FoscamMediaError(
                            f"Recording {rec.clip_id} changed or did not transfer completely "
                            f"(expected {expected_size}, received {received_size}, "
                            f"camera reports {final_size} bytes); retry later"
                        )

                    if rec.remote_thumbnail and not target_thumbnail.is_file():
                        try:
                            await ftp_client.download_file(rec.remote_thumbnail, str(target_thumbnail))
                        except (FoscamMediaError, FoscamConnectionError, OSError) as err:
                            LOGGER.debug("Thumbnail download failed for %s: %s", rec.clip_id, err)

                result = raw_video
                if convert:
                    result = staging / "recording.mp4"
                    await convert_avi_to_mp4(raw_video, result)
                    if (
                        await asyncio.to_thread(_file_size, result) < MIN_CACHED_MP4_BYTES
                        or not await has_video_packets(result)
                    ):
                        raise FoscamMediaError(f"Converted recording {rec.clip_id} contains no usable video")

                rec._duration = await get_video_duration(result)
                await asyncio.to_thread(result.replace, target_video)
                rec.remote_size = expected_size

        return target_video, (target_thumbnail if target_thumbnail.is_file() else None)
