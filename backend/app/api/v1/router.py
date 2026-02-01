from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.market_data import router as market_data_router
from app.api.v1.endpoints.watchlist import router as watchlist_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(watchlist_router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(market_data_router, prefix="/market-data", tags=["market-data"])
