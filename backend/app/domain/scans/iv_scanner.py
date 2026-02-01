from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScanResult:
    ticker: str
    rule_key: str
    priority: str  # p90|p95
    message: str


def scan_iv_for_ticker(*, ticker: str) -> list[ScanResult]:
    raise NotImplementedError("iv scanner not implemented")
