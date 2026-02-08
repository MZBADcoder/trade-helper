import { type MarketBar } from "@/entities/market";
import { type WatchlistItem } from "@/entities/watchlist";

export type DemoTimeframe = "realtime" | "day" | "week" | "month";

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

export function buildDemoBars(ticker: string, timeframe: DemoTimeframe): MarketBar[] {
  const config = timeframeConfig(timeframe);

  const normalized = ticker.toUpperCase();
  const seed = hashCode(`${normalized}-${timeframe}`);
  const rand = seededRandom(seed);
  const bars: MarketBar[] = [];

  const baseDate = new Date();
  if (timeframe === "realtime") {
    baseDate.setUTCSeconds(0, 0);
  } else {
    baseDate.setUTCHours(0, 0, 0, 0);
  }

  const base = 40 + (seed % 240);
  const volatility = config.volatility;
  const drift = ((seed % 7) - 3) / config.driftDivisor;

  let close = base;

  for (let i = config.points - 1; i >= 0; i -= 1) {
    const pointDate = shiftTime(baseDate, timeframe, i, config.multiplier);

    const wave = Math.sin((config.points - i + (seed % 50)) / config.waveDivisor) * volatility;
    const noise = (rand() - 0.5) * volatility * config.noiseFactor;

    const open = Math.max(1, close * (1 + drift + (rand() - 0.5) * config.openNoise));
    close = Math.max(1, open + wave * config.waveImpact + noise);

    const high = Math.max(open, close) * (1 + rand() * config.wickScale);
    const low = Math.min(open, close) * (1 - rand() * config.wickScale);

    const baseVolume = config.baseVolume + (seed % config.volumeJitter);
    const volume = Math.max(1000, baseVolume * (0.6 + rand() * 0.9));

    bars.push({
      ticker: normalized,
      timespan: config.timespan,
      multiplier: config.multiplier,
      start_at: pointDate.toISOString(),
      open: round2(open),
      high: round2(high),
      low: round2(low),
      close: round2(close),
      volume: Math.round(volume),
      vwap: round2((open + high + low + close) / 4),
      trades: Math.round(config.baseTrades + rand() * config.tradeJitter)
    });
  }

  return bars;
}

type DemoTimeframeConfig = {
  timespan: "minute" | "day" | "week" | "month";
  multiplier: number;
  points: number;
  volatility: number;
  waveDivisor: number;
  noiseFactor: number;
  waveImpact: number;
  wickScale: number;
  openNoise: number;
  driftDivisor: number;
  baseVolume: number;
  volumeJitter: number;
  baseTrades: number;
  tradeJitter: number;
};

function timeframeConfig(timeframe: DemoTimeframe): DemoTimeframeConfig {
  switch (timeframe) {
    case "realtime":
      return {
        timespan: "minute",
        multiplier: 5,
        points: 360,
        volatility: 0.7,
        waveDivisor: 18,
        noiseFactor: 1.1,
        waveImpact: 0.12,
        wickScale: 0.006,
        openNoise: 0.003,
        driftDivisor: 3000,
        baseVolume: 280000,
        volumeJitter: 120000,
        baseTrades: 800,
        tradeJitter: 2500
      };
    case "week":
      return {
        timespan: "week",
        multiplier: 1,
        points: 260,
        volatility: 2.4,
        waveDivisor: 14,
        noiseFactor: 1.7,
        waveImpact: 0.27,
        wickScale: 0.028,
        openNoise: 0.017,
        driftDivisor: 560,
        baseVolume: 3500000,
        volumeJitter: 1400000,
        baseTrades: 5000,
        tradeJitter: 18000
      };
    case "month":
      return {
        timespan: "month",
        multiplier: 1,
        points: 180,
        volatility: 3.1,
        waveDivisor: 11,
        noiseFactor: 1.9,
        waveImpact: 0.32,
        wickScale: 0.034,
        openNoise: 0.02,
        driftDivisor: 500,
        baseVolume: 4200000,
        volumeJitter: 1800000,
        baseTrades: 6200,
        tradeJitter: 22000
      };
    case "day":
    default:
      return {
        timespan: "day",
        multiplier: 1,
        points: 320,
        volatility: 1.3,
        waveDivisor: 12,
        noiseFactor: 1.8,
        waveImpact: 0.22,
        wickScale: 0.018,
        openNoise: 0.01,
        driftDivisor: 900,
        baseVolume: 1200000,
        volumeJitter: 500000,
        baseTrades: 3000,
        tradeJitter: 20000
      };
  }
}

function shiftTime(baseDate: Date, timeframe: DemoTimeframe, offset: number, multiplier: number): Date {
  const date = new Date(baseDate);
  switch (timeframe) {
    case "realtime":
      date.setUTCMinutes(baseDate.getUTCMinutes() - offset * multiplier);
      return date;
    case "week":
      date.setUTCDate(baseDate.getUTCDate() - offset * 7 * multiplier);
      return date;
    case "month":
      date.setUTCMonth(baseDate.getUTCMonth() - offset * multiplier);
      return date;
    case "day":
    default:
      date.setUTCDate(baseDate.getUTCDate() - offset * multiplier);
      return date;
  }
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
