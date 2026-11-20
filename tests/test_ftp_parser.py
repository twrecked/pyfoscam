"""Tests for FTP path and filename parsing."""
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from foscam.exceptions import FoscamConnectionError
from foscam.ftp import (
    FoscamFTPClient,
    parse_timestamp_from_filename,
    parse_trigger_from_filename,
)


@pytest.mark.asyncio
async def test_file_size_reads_a_fresh_listing():
    client = FoscamFTPClient("192.168.1.50", "admin", "secret")
    ftp = Mock()
    ftp.list.side_effect = [
        [{"name": "motion.avi", "size": "2048"}],
        [{"name": "motion.avi", "size": 4096}],
        [{"name": "different.avi", "size": 8192}],
    ]
    with patch.object(client, "_connect_sync", return_value=ftp):
        assert await client.file_size("/camera/motion.avi") == 2048
        assert await client.file_size("/camera/motion.avi") == 4096
        with pytest.raises(FoscamConnectionError, match="not found on camera"):
            await client.file_size("/camera/motion.avi")
    assert ftp.list.call_count == 3
    ftp.list.assert_called_with("/camera", extra=True)


def test_parse_timestamp():
    dt1 = parse_timestamp_from_filename("MD20210522_120400.avi")
    assert dt1 == datetime(2021, 5, 22, 12, 4, 0)

    dt2 = parse_timestamp_from_filename("Schedule20231120-083015.avi")
    assert dt2 == datetime(2023, 11, 20, 8, 30, 15)

    dt3 = parse_timestamp_from_filename("snap_20240101_000000.jpg")
    assert dt3 == datetime(2024, 1, 1, 0, 0, 0)

    assert parse_timestamp_from_filename("invalid_filename.avi") is None


def test_parse_trigger():
    assert parse_trigger_from_filename("MD20210522_120400.avi") == "motion"
    assert parse_trigger_from_filename("Schedule20210522-120400.avi") == "schedule"
    assert parse_trigger_from_filename("Manual20210522-120400.avi") == "manual"
    assert parse_trigger_from_filename("Alarm20210522-120400.avi") == "alarm"
    assert parse_trigger_from_filename("random_file.avi") == "unknown"
