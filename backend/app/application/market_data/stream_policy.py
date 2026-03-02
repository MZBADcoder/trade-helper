from __future__ import annotations

SUPPORTED_STREAM_CHANNELS = frozenset({"quote", "trade", "aggregate"})


def allowed_stream_channels(*, realtime_enabled: bool) -> set[str]:
    _ = realtime_enabled
    return set(SUPPORTED_STREAM_CHANNELS)


def default_stream_channels(*, realtime_enabled: bool) -> set[str]:
    return allowed_stream_channels(realtime_enabled=realtime_enabled)


def normalized_delay_minutes(delay_minutes: int) -> int:
    return max(1, int(delay_minutes))


def delayed_latency_message(*, delay_minutes: int) -> str:
    return f"delayed {normalized_delay_minutes(delay_minutes)}min"
