from __future__ import annotations

from app.api.v1 import router as api_v1_router
from app.core.config import settings


def _paths() -> set[str]:
    router = api_v1_router.create_api_router()
    return {route.path for route in router.routes}


def test_api_router_includes_demo_routes_for_dev_by_default(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "dev")
    monkeypatch.setattr(settings, "demo_endpoints_enabled", False)

    paths = _paths()
    assert "/demo/watchlist" in paths
    assert "/demo/market-data/stream" in paths


def test_api_router_hides_demo_routes_in_production_by_default(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "demo_endpoints_enabled", False)

    paths = _paths()
    assert "/demo/watchlist" not in paths
    assert "/demo/market-data/stream" not in paths


def test_api_router_hides_demo_routes_when_env_has_production_whitespace(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", " Production ")
    monkeypatch.setattr(settings, "demo_endpoints_enabled", False)

    paths = _paths()
    assert "/demo/watchlist" not in paths
    assert "/demo/market-data/stream" not in paths


def test_api_router_hides_demo_routes_for_unknown_env_by_default(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "demo_endpoints_enabled", False)

    paths = _paths()
    assert "/demo/watchlist" not in paths
    assert "/demo/market-data/stream" not in paths


def test_api_router_allows_demo_routes_in_production_when_explicitly_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "demo_endpoints_enabled", True)

    paths = _paths()
    assert "/demo/watchlist" in paths
    assert "/demo/market-data/stream" in paths
