import { listTradingDays, type MarketBar, type MarketSnapshot } from "@/entities/market";

import { type StreamMarketMessage, type StreamStatusMessage } from "./streamProtocol";
import { type TimeframeKey, type TimeframeOption } from "./types";

const STREAM_CHANNELS_REALTIME = ["trade", "quote", "aggregate"];
const STREAM_CHANNELS_DELAYED = ["trade", "aggregate"];
const DEFAULT_MARKET_DELAY_MINUTES = 15;

const INTRADAY_LOOKBACK_DAYS = 10;
const INTRADAY_LOAD_WINDOW_DAYS_1M = 3;
const INTRADAY_CHUNK_WINDOW_DAYS_1M = 3;
const LONG_TERM_LOOKBACK_DAYS = 3650;
const MARKET_TIME_ZONE = "America/New_York";
const MARKET_DATE_FORMATTER = new Intl.DateTimeFormat("en-US", {
  timeZone: MARKET_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit"
});

export const TIMEFRAME_OPTIONS: TimeframeOption[] = [
  { key: "1m", label: "1m" },
  { key: "5m", label: "5m" },
  { key: "15m", label: "15m" },
  { key: "60m", label: "60m" },
  { key: "day", label: "Day" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" }
];

type StreamWsBaseUrlParams = {
  wsBaseUrl?: string;
  apiBaseUrl?: string;
};

type MarketRealtimeConfigEnv = {
  realtimeEnabled?: string;
  delayMinutes?: string;
};

export type MarketRealtimeConfig = {
  realtimeEnabled: boolean;
  delayMinutes: number;
};

export type TimeframeQueryConfig = {
  timespan: string;
  multiplier: number;
  useTradingDays: boolean;
  lookbackDays: number;
  initialWindowDays: number;
  refreshWindowDays: number;
  chunkWindowDays: number;
  limit: number;
};

export type DateRange = {
  from: string;
  to: string;
};

export type TradingDateRange = DateRange & {
  lookbackStartDate: string;
  previousTradingDate: string;
};

export function resolveMarketRealtimeConfig(env: MarketRealtimeConfigEnv): MarketRealtimeConfig {
  const realtimeEnabled = parseEnvBoolean(env.realtimeEnabled, true);
  const delayMinutes = parsePositiveInt(env.delayMinutes, DEFAULT_MARKET_DELAY_MINUTES);
  return { realtimeEnabled, delayMinutes };
}

export function streamChannelsForRealtime(realtimeEnabled: boolean): string[] {
  return realtimeEnabled ? STREAM_CHANNELS_REALTIME : STREAM_CHANNELS_DELAYED;
}

export function shouldIgnoreMarketMessage(message: StreamMarketMessage, realtimeEnabled: boolean): boolean {
  return !realtimeEnabled && message.type === "market.quote";
}

export function shouldStopDegradedPollingOnStatus(
  message: StreamStatusMessage,
  realtimeEnabled: boolean
): boolean {
  if (!realtimeEnabled) {
    return message.connectionState === "connected";
  }
  return message.latency === "real-time" && (message.connectionState === null || message.connectionState === "connected");
}

export function dateOffset(days: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function currentMarketDate(): string {
  return formatMarketDate(new Date());
}

export function shiftTradingDate(dateString: string, tradingDays: number): string {
  let current = dateString;
  while (!isTradingDate(current)) {
    current = shiftDate(current, -1);
  }

  if (tradingDays === 0) {
    return current;
  }

  const step = tradingDays > 0 ? 1 : -1;
  let remaining = Math.abs(tradingDays);
  while (remaining > 0) {
    current = shiftDate(current, step);
    if (isTradingDate(current)) {
      remaining -= 1;
    }
  }

  return current;
}

export function previousHistoryDate(dateString: string): string {
  return shiftDate(dateString, -1);
}

export function compareDateString(left: string, right: string): number {
  if (left === right) return 0;
  return left > right ? 1 : -1;
}

export function resolveFetchRange(params: {
  lookbackStartDate: string;
  endDate: string;
  windowDays: number;
}): DateRange {
  const safeWindow = Math.max(1, params.windowDays);
  const candidateFrom = shiftDate(params.endDate, -(safeWindow - 1));
  const from =
    compareDateString(candidateFrom, params.lookbackStartDate) < 0 ? params.lookbackStartDate : candidateFrom;

  return {
    from,
    to: params.endDate
  };
}

export async function resolveTradingFetchRange(params: {
  token: string;
  lookbackDays: number;
  lookbackStartDate?: string;
  endDate: string;
  windowDays: number;
}): Promise<TradingDateRange> {
  const safeLookbackDays = Math.max(1, params.lookbackDays);
  const lookbackTradingDays = await fetchTradingDays({
    token: params.token,
    endDate: params.endDate,
    count: safeLookbackDays
  });
  const normalizedEnd = lookbackTradingDays[lookbackTradingDays.length - 1] ?? shiftTradingDate(params.endDate, 0);
  const resolvedLookbackStartDate =
    params.lookbackStartDate ??
    lookbackTradingDays[0] ??
    shiftTradingDate(normalizedEnd, -(safeLookbackDays - 1));
  const safeWindow = Math.max(1, params.windowDays);
  const candidateFrom =
    lookbackTradingDays[Math.max(0, lookbackTradingDays.length - safeWindow)] ??
    shiftTradingDate(normalizedEnd, -(safeWindow - 1));
  const from =
    compareDateString(candidateFrom, resolvedLookbackStartDate) < 0 ? resolvedLookbackStartDate : candidateFrom;
  const previousTradingDate = await resolvePreviousTradingDate({
    token: params.token,
    dateString: from
  });

  return {
    from,
    to: normalizedEnd,
    lookbackStartDate: resolvedLookbackStartDate,
    previousTradingDate
  };
}

export async function resolveTradingChunkFetchRange(params: {
  token: string;
  lookbackStartDate: string;
  endDate: string;
  windowDays: number;
}): Promise<TradingDateRange> {
  return resolveTradingFetchRange({
    token: params.token,
    lookbackDays: params.windowDays,
    lookbackStartDate: params.lookbackStartDate,
    endDate: params.endDate,
    windowDays: params.windowDays
  });
}

export function marketQueryForTimeframe(timeframe: TimeframeKey): TimeframeQueryConfig {
  switch (timeframe) {
    case "1m":
      return {
        timespan: "minute",
        multiplier: 1,
        useTradingDays: true,
        lookbackDays: INTRADAY_LOOKBACK_DAYS,
        initialWindowDays: INTRADAY_LOAD_WINDOW_DAYS_1M,
        refreshWindowDays: 2,
        chunkWindowDays: INTRADAY_CHUNK_WINDOW_DAYS_1M,
        limit: 5000
      };
    case "5m":
      return {
        timespan: "minute",
        multiplier: 5,
        useTradingDays: true,
        lookbackDays: INTRADAY_LOOKBACK_DAYS,
        initialWindowDays: INTRADAY_LOOKBACK_DAYS,
        refreshWindowDays: 2,
        chunkWindowDays: INTRADAY_LOOKBACK_DAYS,
        limit: 1500
      };
    case "15m":
      return {
        timespan: "minute",
        multiplier: 15,
        useTradingDays: true,
        lookbackDays: INTRADAY_LOOKBACK_DAYS,
        initialWindowDays: INTRADAY_LOOKBACK_DAYS,
        refreshWindowDays: 2,
        chunkWindowDays: INTRADAY_LOOKBACK_DAYS,
        limit: 1000
      };
    case "60m":
      return {
        timespan: "minute",
        multiplier: 60,
        useTradingDays: true,
        lookbackDays: INTRADAY_LOOKBACK_DAYS,
        initialWindowDays: INTRADAY_LOOKBACK_DAYS,
        refreshWindowDays: 3,
        chunkWindowDays: INTRADAY_LOOKBACK_DAYS,
        limit: 500
      };
    case "week":
      return {
        timespan: "week",
        multiplier: 1,
        useTradingDays: false,
        lookbackDays: LONG_TERM_LOOKBACK_DAYS,
        initialWindowDays: LONG_TERM_LOOKBACK_DAYS,
        refreshWindowDays: 180,
        chunkWindowDays: LONG_TERM_LOOKBACK_DAYS,
        limit: 700
      };
    case "month":
      return {
        timespan: "month",
        multiplier: 1,
        useTradingDays: false,
        lookbackDays: LONG_TERM_LOOKBACK_DAYS,
        initialWindowDays: LONG_TERM_LOOKBACK_DAYS,
        refreshWindowDays: 365,
        chunkWindowDays: LONG_TERM_LOOKBACK_DAYS,
        limit: 240
      };
    case "day":
    default:
      return {
        timespan: "day",
        multiplier: 1,
        useTradingDays: false,
        lookbackDays: LONG_TERM_LOOKBACK_DAYS,
        initialWindowDays: LONG_TERM_LOOKBACK_DAYS,
        refreshWindowDays: 60,
        chunkWindowDays: LONG_TERM_LOOKBACK_DAYS,
        limit: 3000
      };
  }
}

export function isIntradayTimeframe(timeframe: TimeframeKey): boolean {
  return timeframe === "1m" || timeframe === "5m" || timeframe === "15m" || timeframe === "60m";
}

export function buildDetailCacheKey(symbol: string, timeframe: TimeframeKey): string {
  return `${symbol}::${timeframe}`;
}

export function isDetailKeyForSymbol(key: string, symbol: string): boolean {
  return key.startsWith(`${symbol}::`);
}

export function normalizeSymbol(value: string | null | undefined): string {
  return (value ?? "").trim().toUpperCase();
}

export function chunkSymbols(symbols: string[], size: number): string[][] {
  if (size <= 0) return [symbols];
  const chunks: string[][] = [];
  for (let index = 0; index < symbols.length; index += size) {
    chunks.push(symbols.slice(index, index + size));
  }
  return chunks;
}

export function createEmptySnapshot(symbol: string): MarketSnapshot {
  return {
    ticker: symbol,
    last: 0,
    change: 0,
    change_pct: 0,
    open: 0,
    high: 0,
    low: 0,
    volume: 0,
    updated_at: new Date(0).toISOString(),
    market_status: "unknown",
    source: "REST"
  };
}

export function buildStreamUrl(): string {
  const base = resolveStreamWsBaseUrl({
    wsBaseUrl: import.meta.env.VITE_MARKET_STREAM_WS_BASE_URL,
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL
  });
  return `${base}/api/v1/market-data/stream`;
}

export function resolveStreamWsBaseUrl(params: StreamWsBaseUrlParams): string {
  const fallbackProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const fallback = `${fallbackProtocol}//${window.location.host}`;

  const direct = normalizeWsBaseUrl(params.wsBaseUrl);
  if (direct) return direct;

  const fromApi = normalizeWsBaseUrl(params.apiBaseUrl);
  if (fromApi) return fromApi;

  return fallback;
}

export function toMillis(value: string): number {
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

export function resolveSnapshotLast(currentLast: number, message: StreamMarketMessage): number {
  if (message.type === "market.trade") {
    return message.last ?? message.price ?? currentLast;
  }
  if (message.type === "market.aggregate") {
    return message.last ?? message.close ?? currentLast;
  }
  return currentLast;
}

export function sortBars(items: MarketBar[]): MarketBar[] {
  return [...items].sort((left, right) => new Date(left.start_at).getTime() - new Date(right.start_at).getTime());
}

export function mergeBarsByStartAt(existing: MarketBar[], incoming: MarketBar[]): MarketBar[] {
  const merged = new Map<string, MarketBar>();
  existing.forEach((bar) => {
    merged.set(bar.start_at, bar);
  });
  incoming.forEach((bar) => {
    merged.set(bar.start_at, bar);
  });

  return sortBars(Array.from(merged.values()));
}

function formatMarketDate(value: Date): string {
  const parts = MARKET_DATE_FORMATTER.formatToParts(value);
  const year = parts.find((part) => part.type === "year")?.value ?? "1970";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}

function shiftDate(dateString: string, days: number): string {
  const date = new Date(`${dateString}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function isTradingDate(dateString: string): boolean {
  const day = new Date(`${dateString}T12:00:00Z`).getUTCDay();
  return day >= 1 && day <= 5;
}

async function fetchTradingDays(params: {
  token: string;
  endDate: string;
  count: number;
}): Promise<string[]> {
  try {
    return await listTradingDays({
      token: params.token,
      end: params.endDate,
      count: Math.max(1, params.count)
    });
  } catch {
    return [];
  }
}

async function resolvePreviousTradingDate(params: {
  token: string;
  dateString: string;
}): Promise<string> {
  const history = await fetchTradingDays({
    token: params.token,
    endDate: params.dateString,
    count: 2
  });
  if (history.length >= 2) {
    return history[0] ?? params.dateString;
  }
  return shiftTradingDate(params.dateString, -1);
}

function normalizeWsBaseUrl(raw: string | undefined): string | null {
  const value = raw?.trim();
  if (!value) return null;

  const hasProtocol = /^[a-z][a-z0-9+.-]*:\/\//i.test(value);
  const candidate = hasProtocol ? value : `ws://${value}`;

  try {
    const parsed = new URL(candidate);
    let protocol = parsed.protocol.toLowerCase();
    if (protocol === "http:") protocol = "ws:";
    if (protocol === "https:") protocol = "wss:";
    if (protocol !== "ws:" && protocol !== "wss:") return null;
    if (!parsed.host) return null;
    return `${protocol}//${parsed.host}`;
  } catch {
    return null;
  }
}

function parseEnvBoolean(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) return fallback;
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "off"].includes(normalized)) return false;
  return fallback;
}

function parsePositiveInt(value: string | undefined, fallback: number): number {
  if (value === undefined) return fallback;
  const normalized = value.trim();
  if (!/^\d+$/.test(normalized)) {
    return fallback;
  }
  const parsed = Number(normalized);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}
