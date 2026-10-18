from datetime import datetime, timezone

import pytest

from app.services.timestamps import iso_timestamp, parse_timestamp


def test_offset_deadline_is_converted_before_mysql_storage():
    instant = parse_timestamp("2026-10-15T20:30:00+08:00")
    assert instant == datetime(2026, 10, 15, 12, 30, tzinfo=timezone.utc)
    stored = instant.replace(tzinfo=None)
    assert iso_timestamp(stored) == "2026-10-15T12:30:00+00:00"
    assert parse_timestamp(iso_timestamp(stored)) == instant


@pytest.mark.parametrize("value", ["", "not-a-date", "2026-99-99"])
def test_invalid_deadline_is_rejected(value):
    with pytest.raises(ValueError):
        parse_timestamp(value)
