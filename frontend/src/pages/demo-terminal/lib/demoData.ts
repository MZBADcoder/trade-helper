import { type MarketBar } from "@/entities/market";
import { type WatchlistItem } from "@/entities/watchlist";

export const DEFAULT_DEMO_WATCHLIST: WatchlistItem[] = [
  { ticker: "AAPL" },
  { ticker: "NVDA" },
  { ticker: "TSLA" },
  { ticker: "MSFT" },
  { ticker: "SPY" }
];

export function loadDemoWatchlist(): WatchlistItem[] {
  if (typeof window === "undefined") {
    return DEFAULT_DEMO_WATCHLIST;
  }

  const raw = window.localStorage.getItem("trader_helper_demo_watchlist");
  if (!raw) {
    return DEFAULT_DEMO_WATCHLIST;
  }

  try {
    const parsed = JSON.parse(raw) as Array<{ ticker?: string }>;
    const clean = parsed
      .map((item) => item.ticker?.toUpperCase().trim())
      .filter((ticker): ticker is string => Boolean(ticker))
      .map((ticker) => ({ ticker }));
    return clean.length ? clean : DEFAULT_DEMO_WATCHLIST;
  } catch {
    return DEFAULT_DEMO_WATCHLIST;
  }
}

export function saveDemoWatchlist(items: WatchlistItem[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem("trader_helper_demo_watchlist", JSON.stringify(items));
}

export function buildDemoBars(ticker: string, days = 300): MarketBar[] {
  const normalized = ticker.toUpperCase();
  const seed = hashCode(normalized);
  const rand = seededRandom(seed);
  const bars: MarketBar[] = [];

  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);

  const base = 40 + (seed % 240);
  const volatility = 1.2 + ((seed % 11) / 10);
  const drift = ((seed % 7) - 3) / 900;

  let close = base;

  for (let i = days - 1; i >= 0; i -= 1) {
    const day = new Date(today);
    day.setUTCDate(today.getUTCDate() - i);

    const wave = Math.sin((days - i + (seed % 50)) / 12) * volatility;
    const noise = (rand() - 0.5) * volatility * 1.8;

    const open = Math.max(1, close * (1 + drift + (rand() - 0.5) * 0.01));
    close = Math.max(1, open + wave * 0.22 + noise);

    const high = Math.max(open, close) * (1 + rand() * 0.018);
    const low = Math.min(open, close) * (1 - rand() * 0.018);

    const baseVolume = 1200000 + (seed % 500000);
    const volume = Math.max(10000, baseVolume * (0.6 + rand() * 0.9));

    bars.push({
      ticker: normalized,
      timespan: "day",
      multiplier: 1,
      start_at: day.toISOString(),
      open: round2(open),
      high: round2(high),
      low: round2(low),
      close: round2(close),
      volume: Math.round(volume),
      vwap: round2((open + high + low + close) / 4),
      trades: Math.round(3000 + rand() * 20000)
    });
  }

  return bars;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function hashCode(input: string): number {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash << 5) - hash + input.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function seededRandom(initialSeed: number): () => number {
  let seed = initialSeed % 2147483647;
  if (seed <= 0) {
    seed += 2147483646;
  }

  return () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
}
