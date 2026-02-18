import { apiRequest, apiRequestWithResponse } from "@/shared/api";

import { type MarketBar, type MarketSnapshot, type MarketSnapshotsPayload } from "../model/types";

type MarketQuery = {
  token: string;
  ticker: string;
  timespan?: string;
  multiplier?: number;
  from?: string;
  to?: string;
  limit?: number;
};

export async function listMarketBars(params: MarketQuery): Promise<MarketBar[]> {
  return apiRequest<MarketBar[]>("/market-data/bars", {
    token: params.token,
    query: {
      ticker: params.ticker,
      timespan: params.timespan,
      multiplier: params.multiplier,
      from: params.from,
      to: params.to,
      limit: params.limit
    }
  });
}

export async function listMarketBarsWithMeta(params: MarketQuery): Promise<{
  items: MarketBar[];
  dataSource: string | null;
}> {
  const { data, response } = await apiRequestWithResponse<MarketBar[]>("/market-data/bars", {
    token: params.token,
    query: {
      ticker: params.ticker,
      timespan: params.timespan,
      multiplier: params.multiplier,
      from: params.from,
      to: params.to,
      limit: params.limit
    }
  });

  return {
    items: data,
    dataSource: response.headers.get("X-Data-Source")
  };
}

export async function listMarketSnapshots(token: string, tickers: string[]): Promise<MarketSnapshot[]> {
  if (!tickers.length) return [];
  const payload = await apiRequest<MarketSnapshotsPayload>("/market-data/snapshots", {
    token,
    query: {
      tickers: tickers.join(",")
    }
  });
  return payload.items;
}
