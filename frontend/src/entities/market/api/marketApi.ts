import { API_BASE, readJson } from "@/shared/api";

import { type MarketBar } from "../model/types";

type MarketQuery = {
  ticker: string;
  timespan?: string;
  multiplier?: number;
  from?: string;
  to?: string;
  limit?: number;
};

export async function listMarketBars(params: MarketQuery): Promise<MarketBar[]> {
  const search = new URLSearchParams();
  search.set("ticker", params.ticker);
  if (params.timespan) search.set("timespan", params.timespan);
  if (params.multiplier) search.set("multiplier", String(params.multiplier));
  if (params.from) search.set("from", params.from);
  if (params.to) search.set("to", params.to);
  if (params.limit) search.set("limit", String(params.limit));

  const resp = await fetch(`${API_BASE}/market-data/bars?${search.toString()}`);
  if (!resp.ok) throw new Error("Failed to load market bars");
  return (await readJson<MarketBar[]>(resp)) ?? [];
}
