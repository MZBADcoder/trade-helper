import { API_BASE, readJson } from "@/shared/api";

import { type WatchlistItem } from "../model/types";

type ErrorPayload = { detail?: string };

export async function listWatchlist(): Promise<WatchlistItem[]> {
  const resp = await fetch(`${API_BASE}/watchlist`);
  if (!resp.ok) throw new Error("Failed to load watchlist");
  return (await readJson<WatchlistItem[]>(resp)) ?? [];
}

export async function addWatchlist(ticker: string): Promise<WatchlistItem> {
  const resp = await fetch(`${API_BASE}/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker })
  });
  const json = await readJson<WatchlistItem | ErrorPayload>(resp);
  if (!resp.ok) throw new Error((json as ErrorPayload | null)?.detail ?? "Failed to add ticker");
  return (json as WatchlistItem) ?? { ticker };
}

export async function deleteWatchlist(ticker: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/watchlist/${encodeURIComponent(ticker)}`, {
    method: "DELETE"
  });
  if (!resp.ok) throw new Error("Failed to delete ticker");
}
