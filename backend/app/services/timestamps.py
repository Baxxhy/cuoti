"""MySQL stores application timestamps in UTC without retaining timezone offsets."""

from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso_timestamp(value: datetime) -> str:
    return as_utc(value).isoformat()


def parse_timestamp(value: str) -> datetime:
    return as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
