"""Tests for media recording objects."""
from datetime import datetime
from pathlib import Path

from foscam.media import FoscamRecording


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
