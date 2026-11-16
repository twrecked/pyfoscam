"""Tests for media recording objects."""
from datetime import datetime
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
async def test_media_library_refresh(tmp_path: Path):
    cam = FoscamCamera("192.168.1.50", "admin", "secret", storage_dir=tmp_path)
    lib = FoscamMediaLibrary(cam, storage_dir=tmp_path)

    fake_records = [
        {
            "clip_id": "MD20261116_100000",
            "filename": "MD20261116_100000.avi",
            "date": datetime.now(),
            "trigger": "motion",
            "remote_video": "/IPCamera/cam/record/20261116/MD20261116_100000.avi",
            "remote_snapshot": "/IPCamera/cam/snap/20261116/snap_20261116_100000.jpg",
            "size": 500000,
        }
    ]

    mock_ftp = AsyncMock()
    mock_ftp.list_media.return_value = ({}, fake_records)
    mock_ftp.__aenter__.return_value = mock_ftp
    mock_ftp.__aexit__.return_value = None

    with patch.object(cam, "start_ftp_server", new_callable=AsyncMock) as mock_start_ftp, \
         patch.object(cam, "get_ftp_client", return_value=mock_ftp):
        records = await lib.refresh()
        assert len(records) == 1
        assert records[0].clip_id == "MD20261116_100000"
        assert lib.captured_total == 1
        assert lib.captured_today == 1
        mock_start_ftp.assert_awaited_once()
