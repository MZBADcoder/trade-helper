from __future__ import annotations

from app.api.v1.dto.watchlist import WatchlistItemCreate, WatchlistItemOut
from app.domain.watchlist.schemas import WatchlistItem, WatchlistItemIn


def to_domain_create(dto: WatchlistItemCreate) -> WatchlistItemIn:
    return WatchlistItemIn(**dto.model_dump())


def to_domain_item(dto: WatchlistItemOut) -> WatchlistItem:
    return WatchlistItem(**dto.model_dump())


def to_dto(item: WatchlistItem) -> WatchlistItemOut:
    return WatchlistItemOut(**item.model_dump())
