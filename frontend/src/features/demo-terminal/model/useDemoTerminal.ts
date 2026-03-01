import React from "react";

import { buildIndicators, type IndicatorBundle, type MarketBar, type MarketSnapshot } from "@/entities/market";
import { type WatchlistItem } from "@/entities/watchlist";

import { listDemoBars, listDemoSnapshots, listDemoWatchlist, resolveDemoStreamWsUrl } from "../api/demoTerminalApi";

export const DEMO_TICKER = "AMD";
export const DEMO_REPLAY_WINDOW_LABEL = "10:00-10:30 ET";

type DemoStreamStatus = "idle" | "connecting" | "connected" | "reconnecting";

export type DemoTerminalModel = {
  watchlist: WatchlistItem[];
  watchlistBusy: boolean;
  watchlistError: string | null;
  bars: MarketBar[];
  indicators: IndicatorBundle | null;
  snapshot: MarketSnapshot | null;
  streamStatus: DemoStreamStatus;
  streamMessage: string | null;
  loading: boolean;
  error: string | null;
  dataSource: string | null;
  activeTicker: string;
  reload: () => Promise<void>;
};

export function useDemoTerminal(): DemoTerminalModel {
  const [watchlist, setWatchlist] = React.useState<WatchlistItem[]>([{ ticker: DEMO_TICKER }]);
  const [watchlistBusy, setWatchlistBusy] = React.useState(false);
  const [watchlistError, setWatchlistError] = React.useState<string | null>(null);

  const [bars, setBars] = React.useState<MarketBar[]>([]);
  const [indicators, setIndicators] = React.useState<IndicatorBundle | null>(null);
  const [snapshot, setSnapshot] = React.useState<MarketSnapshot | null>(null);

  const [streamStatus, setStreamStatus] = React.useState<DemoStreamStatus>("idle");
  const [streamMessage, setStreamMessage] = React.useState<string | null>(null);

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [dataSource, setDataSource] = React.useState<string | null>(null);

  const prevCloseRef = React.useRef<number | null>(null);
  const replayIndexRef = React.useRef<number>(-1);
  const reconnectTimerRef = React.useRef<number | null>(null);
  const wsRef = React.useRef<WebSocket | null>(null);
  const manualCloseRef = React.useRef(false);

  const applyBars = React.useCallback((items: MarketBar[]) => {
    const normalized = normalizeBars(items);
    setBars(normalized);
    setIndicators(normalized.length ? buildIndicators(normalized) : null);
  }, []);

  const reload = React.useCallback(async () => {
    setWatchlistBusy(true);
    setLoading(true);
    setError(null);
    setWatchlistError(null);
    replayIndexRef.current = -1;
    try {
      const [watchlistItems, barsResult, snapshots] = await Promise.all([
        listDemoWatchlist(),
        listDemoBars(DEMO_TICKER),
        listDemoSnapshots([DEMO_TICKER])
      ]);
      const resolvedWatchlist = watchlistItems.length ? watchlistItems : [{ ticker: DEMO_TICKER }];
      setWatchlist(resolvedWatchlist);
      applyBars(barsResult.items);
      setDataSource(barsResult.dataSource);

      const initialSnapshot = snapshots[0] ?? buildSnapshotFromBars(barsResult.items);
      setSnapshot(initialSnapshot);
      prevCloseRef.current =
        initialSnapshot && Number.isFinite(initialSnapshot.last - initialSnapshot.change)
          ? initialSnapshot.last - initialSnapshot.change
          : null;
    } catch (unknownError: unknown) {
      const message = unknownError instanceof Error ? unknownError.message : "Failed to load demo replay data";
      setError(message);
      setWatchlistError(message);
    } finally {
      setWatchlistBusy(false);
      setLoading(false);
    }
  }, [applyBars]);

  React.useEffect(() => {
    void reload();
  }, [reload]);

  React.useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }
    manualCloseRef.current = false;

    const connect = () => {
      if (manualCloseRef.current) return;

      setStreamStatus((previous) => (previous === "idle" ? "connecting" : "reconnecting"));
      const socket = new WebSocket(resolveDemoStreamWsUrl());
      wsRef.current = socket;

      socket.onopen = () => {
        setStreamStatus("connected");
        setError(null);
        socket.send(
          JSON.stringify({
            action: "subscribe",
            symbols: [DEMO_TICKER],
            channels: ["quote", "trade", "aggregate"]
          })
        );
      };

      socket.onmessage = (event) => {
        const message = parseDemoStreamEnvelope(event.data);
        if (!message) return;

        if (message.type === "system.status") {
          if (message.message) {
            setStreamMessage(message.message);
          }
          return;
        }
        if (message.type === "system.error") {
          setError(message.message ?? "Demo stream error");
          return;
        }
        if (message.type === "market.trade") {
          setSnapshot((previous) => {
            if (!previous || previous.ticker !== DEMO_TICKER) return previous;
            const price = message.last ?? message.price;
            if (price === null) return previous;
            const prevClose = prevCloseRef.current ?? previous.last - previous.change;
            const change = price - prevClose;
            const changePct = prevClose === 0 ? 0 : (change / prevClose) * 100;
            return {
              ...previous,
              last: round2(price),
              change: round2(change),
              change_pct: round4(changePct),
              updated_at: message.eventTs
            };
          });
          return;
        }
        if (message.type !== "market.aggregate") return;
        if (message.symbol !== DEMO_TICKER) return;

        const aggregateBar = toBarFromAggregate(message);
        if (!aggregateBar) return;

        setBars((previous) => {
          const merged = mergeBarsByStartAt(previous, [aggregateBar]);
          setIndicators(merged.length ? buildIndicators(merged) : null);
          return merged;
        });

        setSnapshot((previous) => {
          const prevClose =
            prevCloseRef.current ??
            (previous && Number.isFinite(previous.last - previous.change) ? previous.last - previous.change : aggregateBar.open);
          prevCloseRef.current = prevClose;

          const nextReplayIndex = message.replayIndex;
          const replayReset =
            nextReplayIndex !== null && (nextReplayIndex <= replayIndexRef.current || replayIndexRef.current < 0);
          replayIndexRef.current = nextReplayIndex ?? replayIndexRef.current;

          const baseOpen = replayReset || !previous ? aggregateBar.open : previous.open;
          const baseHigh = replayReset || !previous ? aggregateBar.high : Math.max(previous.high, aggregateBar.high);
          const baseLow = replayReset || !previous ? aggregateBar.low : Math.min(previous.low, aggregateBar.low);
          const baseVolume =
            replayReset || !previous ? Math.round(aggregateBar.volume) : previous.volume + Math.round(aggregateBar.volume);

          const change = aggregateBar.close - prevClose;
          const changePct = prevClose === 0 ? 0 : (change / prevClose) * 100;

          return {
            ticker: DEMO_TICKER,
            last: round2(aggregateBar.close),
            change: round2(change),
            change_pct: round4(changePct),
            open: round2(baseOpen),
            high: round2(baseHigh),
            low: round2(baseLow),
            volume: baseVolume,
            updated_at: aggregateBar.start_at,
            market_status: "open",
            source: "DEMO_MOCK"
          };
        });
      };

      socket.onclose = () => {
        wsRef.current = null;
        if (manualCloseRef.current) return;
        setStreamStatus("reconnecting");
        reconnectTimerRef.current = window.setTimeout(connect, 1200);
      };

      socket.onerror = () => {
        setError("Demo stream disconnected");
      };
    };

    connect();

    return () => {
      manualCloseRef.current = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []);

  return {
    watchlist,
    watchlistBusy,
    watchlistError,
    bars,
    indicators,
    snapshot,
    streamStatus,
    streamMessage,
    loading,
    error,
    dataSource,
    activeTicker: DEMO_TICKER,
    reload
  };
}

type DemoStreamStatusEnvelope = {
  type: "system.status";
  message: string | null;
};

type DemoStreamErrorEnvelope = {
  type: "system.error";
  message: string | null;
};

type DemoStreamTradeEnvelope = {
  type: "market.trade";
  symbol: string;
  eventTs: string;
  price: number | null;
  last: number | null;
};

type DemoStreamAggregateEnvelope = {
  type: "market.aggregate";
  symbol: string;
  eventTs: string;
  start_at: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  replayIndex: number | null;
};

type DemoStreamEnvelope =
  | DemoStreamStatusEnvelope
  | DemoStreamErrorEnvelope
  | DemoStreamTradeEnvelope
  | DemoStreamAggregateEnvelope;

function parseDemoStreamEnvelope(raw: unknown): DemoStreamEnvelope | null {
  if (typeof raw !== "string") return null;
  const parsed = parseJsonObject(raw);
  if (!parsed) return null;
  const type = asString(parsed.type);
  if (!type) return null;
  const data = asObject(parsed.data) ?? {};

  if (type === "system.status") {
    return { type, message: asString(data.message) };
  }

  if (type === "system.error") {
    return { type, message: asString(data.message) };
  }

  if (type === "market.trade") {
    const symbol = normalizeSymbol(asString(data.symbol));
    if (!symbol) return null;
    return {
      type,
      symbol,
      eventTs: asString(data.event_ts) ?? new Date().toISOString(),
      price: asNumber(data.price),
      last: asNumber(data.last)
    };
  }

  if (type === "market.aggregate") {
    const symbol = normalizeSymbol(asString(data.symbol));
    const eventTs = asString(data.event_ts);
    const startAt = asString(data.start_at);
    const open = asNumber(data.open);
    const high = asNumber(data.high);
    const low = asNumber(data.low);
    const close = asNumber(data.close);
    const volume = asNumber(data.volume);
    if (!symbol || !eventTs || !startAt || open === null || high === null || low === null || close === null || volume === null) {
      return null;
    }
    return {
      type,
      symbol,
      eventTs,
      start_at: startAt,
      open,
      high,
      low,
      close,
      volume,
      replayIndex: asInteger(data.replay_index)
    };
  }

  return null;
}

function toBarFromAggregate(message: DemoStreamAggregateEnvelope): MarketBar | null {
  if (Number.isNaN(Date.parse(message.start_at))) return null;
  return {
    ticker: message.symbol,
    timespan: "minute",
    multiplier: 1,
    start_at: message.start_at,
    open: round2(message.open),
    high: round2(message.high),
    low: round2(message.low),
    close: round2(message.close),
    volume: Math.max(0, Math.round(message.volume)),
    vwap: round2((message.open + message.high + message.low + message.close) / 4),
    trades: null
  };
}

function normalizeBars(items: MarketBar[]): MarketBar[] {
  return mergeBarsByStartAt([], items);
}

function mergeBarsByStartAt(current: MarketBar[], incoming: MarketBar[]): MarketBar[] {
  const byStartAt = new Map<string, MarketBar>();
  current.forEach((item) => {
    byStartAt.set(item.start_at, item);
  });
  incoming.forEach((item) => {
    byStartAt.set(item.start_at, item);
  });
  return Array.from(byStartAt.values()).sort((a, b) => a.start_at.localeCompare(b.start_at));
}

function buildSnapshotFromBars(items: MarketBar[]): MarketSnapshot | null {
  const bars = normalizeBars(items);
  if (!bars.length) return null;
  const first = bars[0];
  const last = bars[bars.length - 1];
  const high = bars.reduce((value, item) => Math.max(value, item.high), first.high);
  const low = bars.reduce((value, item) => Math.min(value, item.low), first.low);
  const volume = Math.round(bars.reduce((value, item) => value + item.volume, 0));
  const prevClose = first.open;
  const change = last.close - prevClose;
  const changePct = prevClose === 0 ? 0 : (change / prevClose) * 100;

  return {
    ticker: DEMO_TICKER,
    last: round2(last.close),
    change: round2(change),
    change_pct: round4(changePct),
    open: round2(first.open),
    high: round2(high),
    low: round2(low),
    volume,
    updated_at: last.start_at,
    market_status: "open",
    source: "DEMO_MOCK"
  };
}

function parseJsonObject(raw: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      return parsed as Record<string, unknown>;
    }
    return null;
  } catch {
    return null;
  }
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object") {
    return value as Record<string, unknown>;
  }
  return null;
}

function asString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized || null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function asInteger(value: unknown): number | null {
  const parsed = asNumber(value);
  if (parsed === null) return null;
  if (!Number.isInteger(parsed)) return null;
  return parsed;
}

function normalizeSymbol(value: string | null): string {
  return (value ?? "").trim().toUpperCase();
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}
