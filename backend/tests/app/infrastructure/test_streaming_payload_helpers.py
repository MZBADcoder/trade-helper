from __future__ import annotations

from app.infrastructure.streaming.redis_event_bus import _decode_message_payload
from app.infrastructure.streaming.redis_topic_registry import _decode_topics


def test_decode_message_payload_accepts_json_string_and_bytes() -> None:
    payload_from_string = _decode_message_payload('{"type":"market.quote","data":{"symbol":"AAPL"}}')
    payload_from_bytes = _decode_message_payload(b'{"type":"market.trade","data":{"symbol":"AAPL"}}')

    assert payload_from_string is not None
    assert payload_from_string["type"] == "market.quote"
    assert payload_from_bytes is not None
    assert payload_from_bytes["type"] == "market.trade"


def test_decode_message_payload_rejects_invalid_payloads() -> None:
    assert _decode_message_payload(None) is None
    assert _decode_message_payload(123) is None
    assert _decode_message_payload("{not-json") is None
    assert _decode_message_payload("[]") is None


def test_decode_topics_accepts_valid_payload_and_filters_empty_values() -> None:
    topics = _decode_topics(b'{"topics":["Q.AAPL","T.AAPL","","  ","A.AAPL"]}')
    assert topics == {"Q.AAPL", "T.AAPL", "A.AAPL"}


def test_decode_topics_rejects_invalid_payloads() -> None:
    assert _decode_topics(None) == set()
    assert _decode_topics(123) == set()
    assert _decode_topics(b"{not-json") == set()
    assert _decode_topics(b'{"topics":"Q.AAPL"}') == set()

