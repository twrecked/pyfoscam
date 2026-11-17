"""Tests for media recording objects and persistent caching."""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from foscam.client import FoscamCamera
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
    rec.local_video_path.write_bytes(b"dummy mp4")
    rec.local_thumbnail_path.write_bytes(b"dummy jpg")

    assert rec.is_downloaded
    assert rec.is_thumbnail_downloaded

    d = rec.to_dict()
    assert d["clip_id"] == "MD20210522_120400"
    assert d["is_downloaded"] is True
    assert d["remote_size"] == 1048576


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
