import { API_BASE, apiRequest, apiRequestWithResponse } from "@/shared/api";

import { type MarketBar, type MarketSnapshot } from "@/entities/market";
import { type WatchlistItem } from "@/entities/watchlist";

export async function listDemoWatchlist(): Promise<WatchlistItem[]> {
  return apiRequest<WatchlistItem[]>("/demo/watchlist");
}

export async function listDemoBars(ticker: string): Promise<{ items: MarketBar[]; dataSource: string | null }> {
  const { data, response } = await apiRequestWithResponse<MarketBar[] | undefined>("/demo/market-data/bars", {
    query: {
      ticker,
      timespan: "minute",
      multiplier: 1
    }
  });

  return {
    items: data ?? [],
    dataSource: response.headers.get("X-Data-Source")
  };
}

export async function listDemoSnapshots(tickers: string[]): Promise<MarketSnapshot[]> {
  if (!tickers.length) return [];

  const payload = await apiRequest<{ items: MarketSnapshot[] }>("/demo/market-data/snapshots", {
    query: {
      tickers: tickers.join(",")
    }
  });
  return payload.items ?? [];
}

export function resolveDemoStreamWsUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${API_BASE}/demo/market-data/stream`;
}
