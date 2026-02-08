import { apiRequest } from "@/shared/api";

import { type WatchlistItem } from "../model/types";

export async function listWatchlist(token: string): Promise<WatchlistItem[]> {
  return apiRequest<WatchlistItem[]>("/watchlist", { token });
}

export async function addWatchlist(token: string, ticker: string): Promise<WatchlistItem> {
  return apiRequest<WatchlistItem>("/watchlist", {
    method: "POST",
    token,
    body: { ticker }
  });
}

export async function deleteWatchlist(token: string, ticker: string): Promise<{ deleted: string }> {
  return apiRequest<{ deleted: string }>(`/watchlist/${encodeURIComponent(ticker)}`, {
    method: "DELETE",
    token
  });
}
