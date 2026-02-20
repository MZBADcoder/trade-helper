from __future__ import annotations

from app.application.market_data.stream_session import MarketStreamSession, parse_stream_action


def test_parse_stream_action_returns_none_for_invalid_payload() -> None:
    assert parse_stream_action("invalid-json") is None
    assert parse_stream_action("[]") is None
    assert parse_stream_action('{"symbols":["AAPL"]}') is None
    assert parse_stream_action('{"action":"subscribe","channels":"quote"}') is None


def test_parse_stream_action_normalizes_symbols_and_channels() -> None:
    action = parse_stream_action(
        '{"action":"subscribe","symbols":["aapl"," MSFT ","@@bad"],"channels":["Quote","trade"]}'
    )
    assert action is not None
    assert action.action == "subscribe"
    assert action.symbols == {"AAPL", "MSFT"}
    assert action.channels == {"quote", "trade"}


def test_session_apply_action_enforces_watchlist_and_symbol_limit() -> None:
    session = MarketStreamSession(
        max_symbols=2,
        ping_interval_seconds=20,
        ping_timeout_seconds=10,
        ping_max_misses=2,
        now=0.0,
    )

    parsed = parse_stream_action('{"action":"subscribe","symbols":["AAPL","MSFT","NVDA"]}')
    assert parsed is not None
    blocked = session.apply_action(parsed, allowed_symbols={"AAPL", "MSFT"}, now=1.0)
    assert blocked.error is not None
    assert blocked.error.code == "STREAM_SYMBOL_NOT_ALLOWED"

    parsed_limit = parse_stream_action('{"action":"subscribe","symbols":["AAPL","MSFT","NVDA"]}')
    assert parsed_limit is not None
    limited = session.apply_action(parsed_limit, allowed_symbols={"AAPL", "MSFT", "NVDA"}, now=1.5)
    assert limited.error is not None
    assert limited.error.code == "STREAM_SUBSCRIPTION_LIMIT_EXCEEDED"


def test_session_rejects_channel_not_allowed_in_delayed_mode() -> None:
    session = MarketStreamSession(
        max_symbols=5,
        ping_interval_seconds=20,
        ping_timeout_seconds=10,
        ping_max_misses=2,
        allowed_channels={"trade", "aggregate"},
        default_channels={"trade", "aggregate"},
        now=0.0,
    )
    assert session.channels == {"trade", "aggregate"}

    parsed = parse_stream_action('{"action":"subscribe","symbols":["AAPL"],"channels":["quote"]}')
    assert parsed is not None
    outcome = session.apply_action(parsed, allowed_symbols={"AAPL"}, now=1.0)
    assert outcome.error is not None
    assert outcome.error.code == "STREAM_CHANNEL_NOT_ALLOWED"
    assert outcome.channels == {"trade", "aggregate"}


def test_session_heartbeat_closes_after_max_misses() -> None:
    session = MarketStreamSession(
        max_symbols=100,
        ping_interval_seconds=2,
        ping_timeout_seconds=1,
        ping_max_misses=2,
        now=0.0,
    )

    first_ping = session.heartbeat_decision(now=2.0)
    assert first_ping.should_send_ping is True
    assert first_ping.should_close is False
    session.mark_ping_sent(sent_at=2.0)

    first_miss = session.heartbeat_decision(now=3.1)
    assert first_miss.should_close is False

    second_ping = session.heartbeat_decision(now=4.0)
    assert second_ping.should_send_ping is True
    assert second_ping.should_close is False
    session.mark_ping_sent(sent_at=4.0)

    second_miss = session.heartbeat_decision(now=5.1)
    assert second_miss.should_close is True
