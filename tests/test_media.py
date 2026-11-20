"""Tests for media recording objects and persistent caching."""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from foscam.client import FoscamCamera
from foscam.exceptions import FoscamMediaError
from foscam.media import FoscamMediaLibrary, FoscamRecording


def test_recording_properties(tmp_path: Path):
    rec = FoscamRecording(
        clip_id="MD20210522_120400",
        created_at=datetime(2021, 5, 22, 12, 4, 0),
        remote_video="/IPCamera/001122334455/record/20210522/MD20210522_120400.avi",
        remote_thumbnail="/IPCamera/001122334455/snap/20210522/snap_20210522_120400.jpg",
        remote_size=1048576,
        trigger="motion",
        storage_dir=tmp_path,
    )

    assert rec.clip_id == "MD20210522_120400"
    assert rec.created_at_pretty() == "05-22 12:04:00"
    assert rec.local_video_path == tmp_path / "MD20210522_120400.mp4"
    assert rec.local_raw_path == tmp_path / "MD20210522_120400.avi"
    assert rec.local_thumbnail_path == tmp_path / "MD20210522_120400.jpg"
    assert not rec.is_downloaded
    assert not rec.is_thumbnail_downloaded

    # Create dummy local files
    rec.local_video_path.write_bytes(b"\0" * 262)
    assert not rec.is_downloaded
    rec.local_video_path.write_bytes(b"\0" * 1024)
    rec.local_thumbnail_path.write_bytes(b"dummy jpg")

    assert rec.is_downloaded
    assert rec.is_thumbnail_downloaded

    d = rec.to_dict()
    assert d["clip_id"] == "MD20210522_120400"
    assert d["is_downloaded"] is True
    assert d["remote_size"] == 1048576


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sizes", "received", "has_video", "error"),
    [
        ([0], 0, True, "empty"),
        ([2048, 4096], 0, True, "still growing"),
        ([4096, 4096, 4096], 2048, True, "did not transfer completely"),
        ([4096, 4096, 8192], 4096, True, "did not transfer completely"),
        ([4096, 4096, 4096], 4096, False, "contains no usable video"),
        ([4096, 4096, 4096], 4096, True, None),
    ],
)
async def test_download_waits_and_only_publishes_verified_video(
    tmp_path: Path, sizes: list[int], received: int, has_video: bool, error: str | None
):
    cam = FoscamCamera("192.168.1.50", "admin", "secret", storage_dir=tmp_path)
    lib = FoscamMediaLibrary(cam, storage_dir=tmp_path)
    rec = FoscamRecording(
        "motion", datetime.now(), "/camera/motion.avi", None, 2048, storage_dir=tmp_path
    )
    legacy_data = bytes(262)
    rec.local_video_path.write_bytes(legacy_data)

    async def download(_remote: str, local: str) -> None:
        Path(local).write_bytes(bytes(received))

    async def convert(_raw: Path, output: Path) -> None:
        assert rec.local_video_path.read_bytes() == legacy_data
        output.write_bytes(bytes(1024))

    ftp = AsyncMock()
    ftp.__aenter__.return_value = ftp
    ftp.file_size.side_effect = sizes
    ftp.download_file.side_effect = download
    with (
        patch.object(cam, "start_ftp_server", new_callable=AsyncMock),
        patch.object(cam, "get_ftp_client", return_value=ftp),
        patch("foscam.media.asyncio.sleep", new_callable=AsyncMock) as sleep,
        patch("foscam.media.is_ffmpeg_available", return_value=True),
        patch("foscam.media.is_ffprobe_available", return_value=True),
        patch("foscam.media.convert_avi_to_mp4", side_effect=convert) as remux,
        patch("foscam.media.has_video_packets", return_value=has_video),
        patch("foscam.media.get_video_duration", return_value=30),
    ):
        if error is None:
            assert await lib.download_recording(rec) == (rec.local_video_path, None)
            assert rec.is_downloaded
            assert rec.duration == 30
            assert rec.remote_size == 4096
        else:
            with pytest.raises(FoscamMediaError, match=error):
                await lib.download_recording(rec)
            assert rec.local_video_path.read_bytes() == legacy_data
            assert not rec.is_downloaded
        if sizes[0]:
            sleep.assert_awaited_once_with(10)
        if len(sizes) < 3:
            ftp.download_file.assert_not_awaited()
        if len(sizes) < 3 or received != sizes[1] or sizes[2] != sizes[1]:
            remux.assert_not_awaited()
    assert not list(tmp_path.glob(".foscam-*"))


@pytest.mark.asyncio
async def test_media_library_refresh_and_cache(tmp_path: Path):
    cam = FoscamCamera("192.168.1.50", "admin", "secret", storage_dir=tmp_path)
    lib = FoscamMediaLibrary(cam, storage_dir=tmp_path)

    yesterday = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y%m%d")

    fake_records = [
        {
            "clip_id": f"MD{yesterday_str}_100000",
            "filename": f"MD{yesterday_str}_100000.avi",
            "date": yesterday,
            "trigger": "motion",
            "remote_video": f"/IPCamera/cam/record/{yesterday_str}/MD{yesterday_str}_100000.avi",
            "remote_snapshot": f"/IPCamera/cam/snap/{yesterday_str}/snap_{yesterday_str}_100000.jpg",
            "size": 500000,
        }
    ]

    mock_ftp = AsyncMock()
    mock_ftp.list_media.return_value = ({}, fake_records)
    mock_ftp.__aenter__.return_value = mock_ftp
    mock_ftp.__aexit__.return_value = None

    with patch.object(cam, "start_ftp_server", new_callable=AsyncMock), \
         patch.object(cam, "get_ftp_client", return_value=mock_ftp):
        # 1. Initial refresh -> populates cache file
        records = await lib.refresh()
        assert len(records) == 1
        assert lib.cache_path.is_file()

        # 2. Second refresh -> yesterday should now be passed in skip_dates!
        mock_ftp.list_media.return_value = ({}, [])
        records2 = await lib.refresh()
        assert len(records2) == 1
        assert records2[0].clip_id == f"MD{yesterday_str}_100000"

        # Verify skip_dates was passed with yesterday_str
        call_args = mock_ftp.list_media.call_args[1]
        assert yesterday_str in call_args["skip_dates"]

        # 3. Clear cache
        await lib.clear_cache()
        assert not lib.cache_path.is_file()
        assert len(lib.recordings) == 0


@pytest.mark.asyncio
async def test_prune_local_recordings(tmp_path: Path):
    cam = FoscamCamera("192.168.1.50", "admin", "secret", storage_dir=tmp_path)
    lib = FoscamMediaLibrary(cam, storage_dir=tmp_path)

    # 1. Old files (should be pruned)
    old_mp4 = tmp_path / "MD20200101_120000.mp4"
    old_mp4.write_bytes(b"old video content")
    old_jpg = tmp_path / "MD20200101_120000.jpg"
    old_jpg.write_bytes(b"old thumbnail content")

    # 2. Recent file (today, should NOT be pruned)
    today_str = datetime.now().strftime("%Y%m%d")
    recent_mp4 = tmp_path / f"MD{today_str}_120000.mp4"
    recent_mp4.write_bytes(b"recent video content")

    # 3. Hidden cache file (should NOT be pruned)
    cache_file = tmp_path / ".cache_192_168_1_50.json"
    cache_file.write_bytes(b"{}")

    # Dry run test
    deleted, freed = await lib.prune_local(days=30, dry_run=True)
    assert deleted == 2
    assert freed == len(b"old video content") + len(b"old thumbnail content")
    assert old_mp4.is_file()
    assert old_jpg.is_file()

    # Actual prune
    deleted, freed = await lib.prune_local(days=30, dry_run=False)
    assert deleted == 2
    assert not old_mp4.is_file()
    assert not old_jpg.is_file()
    assert recent_mp4.is_file()
    assert cache_file.is_file()
