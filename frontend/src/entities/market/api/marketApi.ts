import { apiRequest } from "@/shared/api";

import { type MarketBar } from "../model/types";

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
