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
