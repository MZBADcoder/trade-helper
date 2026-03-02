from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.demo_market_data import router as demo_market_data_router
from app.api.v1.endpoints.demo_market_data_stream import router as demo_market_data_stream_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.market_data import router as market_data_rest_router
from app.api.v1.endpoints.market_data_stream import router as market_data_stream_router
from app.api.v1.endpoints.options import router as options_router
from app.api.v1.endpoints.watchlist import router as watchlist_router
from app.core.config import settings


def _demo_endpoints_enabled() -> bool:
    if settings.demo_endpoints_enabled:
        return True
    return settings.normalized_app_env in {"dev", "development", "local", "test", "testing"}


def create_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health_router, tags=["health"])
    router.include_router(auth_router, prefix="/auth", tags=["auth"])
    router.include_router(watchlist_router, prefix="/watchlist", tags=["watchlist"])
    router.include_router(market_data_rest_router, prefix="/market-data", tags=["market-data"])
    router.include_router(market_data_stream_router, prefix="/market-data", tags=["market-data"])
    router.include_router(options_router, prefix="/options", tags=["options"])
    if _demo_endpoints_enabled():
        router.include_router(demo_market_data_router, prefix="/demo", tags=["demo"])
        router.include_router(demo_market_data_stream_router, prefix="/demo", tags=["demo"])
    return router


api_router = create_api_router()
