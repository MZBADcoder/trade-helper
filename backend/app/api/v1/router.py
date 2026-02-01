from fastapi import APIRouter

from app.api.v1.endpoints.alerts import router as alerts_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.market_data import router as market_data_router
from app.api.v1.endpoints.rules import router as rules_router
from app.api.v1.endpoints.scans import router as scans_router
from app.api.v1.endpoints.watchlist import router as watchlist_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(watchlist_router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(rules_router, prefix="/rules", tags=["rules"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
api_router.include_router(scans_router, prefix="/scans", tags=["scans"])
api_router.include_router(market_data_router, prefix="/market-data", tags=["market-data"])
