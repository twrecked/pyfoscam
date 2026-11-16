"""Tests for FTP path and filename parsing."""
from datetime import datetime

from foscam.ftp import (
    parse_timestamp_from_filename,
    parse_trigger_from_filename,
)


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
