export type MarketBar = {
  ticker: string;
  timespan: string;
  multiplier: number;
  start_at: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap?: number | null;
  trades?: number | null;
};

export type MarketSnapshot = {
  ticker: string;
  last: number;
  change: number;
  change_pct: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  updated_at: string;
  market_status: string;
  source: string;
};

export type MarketSnapshotsPayload = {
  items: MarketSnapshot[];
};
