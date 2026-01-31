export type Alert = {
  id: number;
  ticker: string;
  rule_key: string;
  priority: string;
  message: string;
  created_at?: string | null;
};

export type WatchlistItem = { ticker: string };

const API = "/api/v1";

export async function listAlerts(): Promise<Alert[]> {
  const resp = await fetch(`${API}/alerts?limit=50`);
  if (!resp.ok) throw new Error("Failed to load alerts");
  return resp.json();
}

export async function listWatchlist(): Promise<WatchlistItem[]> {
  const resp = await fetch(`${API}/watchlist`);
  if (!resp.ok) throw new Error("Failed to load watchlist");
  return resp.json();
}

export async function addWatchlist(ticker: string): Promise<WatchlistItem> {
  const resp = await fetch(`${API}/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker })
  });
  const json = await resp.json();
  if (!resp.ok) throw new Error(json?.detail ?? "Failed to add ticker");
  return json;
}

export async function deleteWatchlist(ticker: string): Promise<void> {
  const resp = await fetch(`${API}/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" });
  if (!resp.ok) throw new Error("Failed to delete ticker");
}

export async function enqueueScan(): Promise<{ task_id: string }> {
  const resp = await fetch(`${API}/scans/enqueue`, { method: "POST" });
  if (!resp.ok) throw new Error("Failed to enqueue scan");
  return resp.json();
}

