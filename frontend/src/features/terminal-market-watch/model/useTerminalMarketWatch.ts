import React from "react";

import {
  buildIndicators,
  listMarketBarsWithMeta,
  listMarketSnapshots,
  type MarketSnapshot
} from "@/entities/market";
import { useSession } from "@/entities/session";
import { addWatchlist, deleteWatchlist, listWatchlist, type WatchlistItem } from "@/entities/watchlist";

import {
  type DetailSnapshot,
  type StreamStatus,
  type TimeframeKey,
  type TimeframeOption,
  type TerminalMarketWatchViewModel
} from "./types";
import { parseStreamEnvelope, type StreamMarketMessage, type StreamStatusMessage } from "./streamProtocol";

export const TIMEFRAME_OPTIONS: TimeframeOption[] = [
  { key: "5m", label: "5m" },
  { key: "15m", label: "15m" },
  { key: "60m", label: "60m" },
  { key: "day", label: "Day" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" }
];

const STREAM_CHANNELS = ["trade", "quote", "aggregate"];
const SNAPSHOT_POLL_INTERVAL_MS = 4_000;
const BARS_POLL_INTERVAL_MS = 20_000;
const RECONNECT_MAX_DELAY_MS = 10_000;

export function useTerminalMarketWatch(): TerminalMarketWatchViewModel {
  const { token, user } = useSession();

  const [watchlist, setWatchlist] = React.useState<WatchlistItem[]>([]);
  const [watchlistBusy, setWatchlistBusy] = React.useState(false);
  const [watchlistError, setWatchlistError] = React.useState<string | null>(null);
  const [tickerInput, setTickerInput] = React.useState("");

  const [activeTicker, setActiveTicker] = React.useState<string | null>(null);
  const [timeframe, setTimeframe] = React.useState<TimeframeKey>("day");
  const [detailsByTicker, setDetailsByTicker] = React.useState<Record<string, DetailSnapshot>>({});
  const detailsRef = React.useRef<Record<string, DetailSnapshot>>({});

  const [snapshotMap, setSnapshotMap] = React.useState<Record<string, MarketSnapshot>>({});
  const snapshotTsRef = React.useRef<Record<string, number>>({});

  const [streamStatus, setStreamStatus] = React.useState<StreamStatus>("idle");
  const [streamSource, setStreamSource] = React.useState<"WS" | "REST">("REST");
  const [dataLatency, setDataLatency] = React.useState<"real-time" | "delayed">("delayed");
  const [lastSyncAt, setLastSyncAt] = React.useState<string | null>(null);
  const [lastError, setLastError] = React.useState<string | null>(null);

  const activeTickerRef = React.useRef<string | null>(null);
  const tokenRef = React.useRef<string | null>(null);
  const desiredSubscriptionsRef = React.useRef<string[]>([]);

  const refreshSnapshotsRef = React.useRef<(symbols?: string[]) => Promise<void>>(async () => undefined);
  const loadTickerDetailRef = React.useRef<(ticker: string, force?: boolean) => Promise<void>>(async () => undefined);

  const wsRef = React.useRef<WebSocket | null>(null);
  const reconnectAttemptRef = React.useRef(0);
  const reconnectTimerRef = React.useRef<number | null>(null);
  const snapshotPollRef = React.useRef<number | null>(null);
  const barsPollRef = React.useRef<number | null>(null);
  const manualCloseRef = React.useRef(false);
  const subscriptionSetRef = React.useRef<Set<string>>(new Set());

  React.useEffect(() => {
    detailsRef.current = detailsByTicker;
  }, [detailsByTicker]);

  React.useEffect(() => {
    activeTickerRef.current = activeTicker;
  }, [activeTicker]);

  React.useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const mergeSnapshots = React.useCallback((items: MarketSnapshot[], source: "REST" | "WS") => {
    if (!items.length) return;

    setSnapshotMap((previous) => {
      const next = { ...previous };

      items.forEach((item) => {
        const symbol = normalizeSymbol(item.ticker);
        if (!symbol) return;

        const incomingAt = item.updated_at || new Date().toISOString();
        const incomingTs = toMillis(incomingAt);
        const knownTs = snapshotTsRef.current[symbol] ?? 0;
        if (incomingTs < knownTs) return;

        snapshotTsRef.current[symbol] = incomingTs;
        next[symbol] = {
          ...item,
          ticker: symbol,
          updated_at: incomingAt,
          source: item.source || source
        };
      });

      return next;
    });
  }, []);

  const applyStreamMarketMessage = React.useCallback((message: StreamMarketMessage) => {
    const symbol = message.symbol;
    const eventAt = message.eventTs;
    const incomingTs = toMillis(eventAt);
    const knownTs = snapshotTsRef.current[symbol] ?? 0;
    if (incomingTs < knownTs) {
      return;
    }

    snapshotTsRef.current[symbol] = incomingTs;

    setSnapshotMap((previous) => {
      const base = previous[symbol] ?? createEmptySnapshot(symbol);
      const nextLast = resolveSnapshotLast(base.last, message);
      const nextOpen = message.type === "market.aggregate" ? (message.open ?? base.open) : base.open;
      const nextHigh = message.type === "market.aggregate" ? (message.high ?? base.high) : base.high;
      const nextLow = message.type === "market.aggregate" ? (message.low ?? base.low) : base.low;
      const nextVolume = message.type === "market.aggregate" ? (message.volume ?? base.volume) : base.volume;

      return {
        ...previous,
        [symbol]: {
          ...base,
          last: nextLast,
          open: nextOpen,
          high: nextHigh,
          low: nextLow,
          volume: nextVolume,
          updated_at: eventAt,
          source: "WS"
        }
      };
    });

    setDetailsByTicker((previous) => {
      const detail = previous[symbol];
      if (!detail) return previous;
      return {
        ...previous,
        [symbol]: {
          ...detail,
          updatedAt: eventAt,
          source: "WS"
        }
      };
    });

    setLastSyncAt(eventAt);
  }, []);

  const refreshWatchlist = React.useCallback(async () => {
    if (!token) return;

    setWatchlistBusy(true);
    setWatchlistError(null);

    try {
      const items = await listWatchlist(token);
      const normalized = items.map((item) => ({ ...item, ticker: normalizeSymbol(item.ticker) }));

      setWatchlist(normalized);
      setActiveTicker((current) => {
        if (!normalized.length) return null;
        if (current && normalized.some((item) => item.ticker === current)) {
          return current;
        }
        return normalized[0].ticker;
      });
    } catch (error: any) {
      setWatchlistError(error?.message ?? "Failed to load watchlist.");
    } finally {
      setWatchlistBusy(false);
    }
  }, [token]);

  const refreshSnapshots = React.useCallback(
    async (symbols?: string[]) => {
      if (!token) return;

      const targets = (symbols ?? watchlist.map((item) => item.ticker)).map(normalizeSymbol).filter(Boolean);
      if (!targets.length) return;

      try {
        const batches = chunkSymbols(targets, 50);
        const responses = await Promise.all(batches.map((batch) => listMarketSnapshots(token, batch)));
        const snapshots = responses.flat();
        mergeSnapshots(snapshots, "REST");
        setLastSyncAt(new Date().toISOString());

        if (streamStatus !== "connected") {
          setStreamSource("REST");
          setDataLatency("delayed");
        }
      } catch (error: any) {
        setLastError(error?.message ?? "Failed to refresh snapshots.");
      }
    },
    [mergeSnapshots, streamStatus, token, watchlist]
  );

  const loadTickerDetail = React.useCallback(
    async (ticker: string, force = false) => {
      if (!token) return;

      const symbol = normalizeSymbol(ticker);
      const existing = detailsRef.current[symbol];
      const isSameTimeframe = existing?.timeframe === timeframe;

      if (!force && isSameTimeframe && existing?.bars.length) {
        return;
      }

      setDetailsByTicker((previous) => ({
        ...previous,
        [symbol]: {
          bars: previous[symbol]?.bars ?? [],
          indicators: previous[symbol]?.indicators ?? null,
          timeframe,
          loading: true,
          error: null,
          updatedAt: previous[symbol]?.updatedAt ?? null,
          source: previous[symbol]?.source ?? null,
          barsDataSource: previous[symbol]?.barsDataSource ?? null
        }
      }));

      try {
        const query = marketQueryForTimeframe(timeframe);
        const payload = await listMarketBarsWithMeta({
          token,
          ticker: symbol,
          timespan: query.timespan,
          multiplier: query.multiplier,
          from: dateOffset(query.fromDays),
          to: dateOffset(0),
          limit: query.limit
        });

        const bars = payload.items;
        const sortedBars = [...bars].sort(
          (left, right) => new Date(left.start_at).getTime() - new Date(right.start_at).getTime()
        );

        setDetailsByTicker((previous) => ({
          ...previous,
          [symbol]: {
            bars: sortedBars,
            indicators: buildIndicators(sortedBars),
            timeframe,
            loading: false,
            error: null,
            updatedAt: new Date().toISOString(),
            source: "REST",
            barsDataSource: payload.dataSource
          }
        }));
      } catch (error: any) {
        setDetailsByTicker((previous) => ({
          ...previous,
          [symbol]: {
            bars: previous[symbol]?.bars ?? [],
            indicators: previous[symbol]?.indicators ?? null,
            timeframe,
            loading: false,
            error: error?.message ?? `Failed to load ${symbol}`,
            updatedAt: previous[symbol]?.updatedAt ?? null,
            source: previous[symbol]?.source ?? null,
            barsDataSource: previous[symbol]?.barsDataSource ?? null
          }
        }));
      }
    },
    [timeframe, token]
  );

  React.useEffect(() => {
    refreshSnapshotsRef.current = refreshSnapshots;
  }, [refreshSnapshots]);

  React.useEffect(() => {
    loadTickerDetailRef.current = loadTickerDetail;
  }, [loadTickerDetail]);

  const stopDegradedPolling = React.useCallback(() => {
    if (snapshotPollRef.current !== null) {
      window.clearInterval(snapshotPollRef.current);
      snapshotPollRef.current = null;
    }
    if (barsPollRef.current !== null) {
      window.clearInterval(barsPollRef.current);
      barsPollRef.current = null;
    }
  }, []);

  const startDegradedPolling = React.useCallback(() => {
    if (snapshotPollRef.current === null) {
      snapshotPollRef.current = window.setInterval(() => {
        void refreshSnapshotsRef.current();
      }, SNAPSHOT_POLL_INTERVAL_MS);
    }

    if (barsPollRef.current === null) {
      barsPollRef.current = window.setInterval(() => {
        const symbol = activeTickerRef.current;
        if (!symbol) return;
        void loadTickerDetailRef.current(symbol, true);
      }, BARS_POLL_INTERVAL_MS);
    }
  }, []);

  const syncSubscriptions = React.useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const desiredSet = new Set(
      desiredSubscriptionsRef.current
        .map((item) => normalizeSymbol(item))
        .filter((item): item is string => Boolean(item))
    );

    const currentSet = subscriptionSetRef.current;
    const toUnsubscribe = [...currentSet].filter((symbol) => !desiredSet.has(symbol));
    const toSubscribe = [...desiredSet].filter((symbol) => !currentSet.has(symbol));

    try {
      if (toUnsubscribe.length) {
        ws.send(
          JSON.stringify({
            action: "unsubscribe",
            symbols: toUnsubscribe,
            channels: STREAM_CHANNELS
          })
        );
      }

      if (toSubscribe.length) {
        ws.send(
          JSON.stringify({
            action: "subscribe",
            symbols: toSubscribe,
            channels: STREAM_CHANNELS
          })
        );
      }

      subscriptionSetRef.current = desiredSet;
    } catch {
      setLastError("订阅更新失败，等待连接恢复后重试。");
    }
  }, []);

  const setDegradedMode = React.useCallback(
    (status: StreamStatus = "degraded") => {
      setStreamStatus(status);
      setStreamSource("REST");
      setDataLatency("delayed");
      startDegradedPolling();
    },
    [startDegradedPolling]
  );

  const applySystemStatus = React.useCallback(
    (message: StreamStatusMessage) => {
      if (message.latency) {
        setDataLatency(message.latency);
      }

      const isRealtime =
        message.latency === "real-time" && (message.connectionState === null || message.connectionState === "connected");
      if (isRealtime) {
        stopDegradedPolling();
        setStreamStatus("connected");
        setStreamSource("WS");
        setDataLatency("real-time");
        return;
      }

      if (message.connectionState === "connected" && message.latency !== "delayed") {
        return;
      }

      setDegradedMode();

      if (message.message) {
        setLastError(message.message);
      }
    },
    [setDegradedMode, stopDegradedPolling]
  );

  const handleStreamMessage = React.useCallback(
    (raw: string) => {
      const message = parseStreamEnvelope(raw);
      if (!message) return;

      if (message.type === "system.ping") {
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ action: "pong" }));
        }
        return;
      }

      if (message.type === "system.status") {
        applySystemStatus(message);
        return;
      }

      if (message.type === "system.error") {
        const errorMessage = message.message ?? "stream error";
        setLastError(message.code ? `${message.code}: ${errorMessage}` : errorMessage);
        if (message.code === "STREAM_UPSTREAM_UNAVAILABLE") {
          setDegradedMode();
        }
        return;
      }

      applyStreamMarketMessage(message);
    },
    [applyStreamMarketMessage, applySystemStatus, setDegradedMode]
  );

  const connectStream = React.useCallback(() => {
    const accessToken = tokenRef.current;
    if (!accessToken) return;

    const current = wsRef.current;
    if (current && (current.readyState === WebSocket.OPEN || current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setStreamStatus((previous) =>
      previous === "idle" || previous === "disconnected" ? "connecting" : "reconnecting"
    );

    const ws = new WebSocket(buildStreamUrl(accessToken));
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptRef.current = 0;

      stopDegradedPolling();
      setStreamStatus("connected");
      setStreamSource("REST");
      setDataLatency("delayed");
      setLastError(null);
      setLastSyncAt(new Date().toISOString());

      syncSubscriptions();

      const symbol = activeTickerRef.current;
      if (symbol) {
        void loadTickerDetailRef.current(symbol, true);
      }
    };

    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        handleStreamMessage(event.data);
      }
    };

    ws.onerror = () => {
      if (!manualCloseRef.current) {
        setLastError("实时连接异常，正在尝试重连。");
      }
    };

    ws.onclose = (event) => {
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
      subscriptionSetRef.current = new Set();

      if (manualCloseRef.current || !tokenRef.current) {
        setStreamStatus("disconnected");
        return;
      }

      if (event.code === 4401) {
        setStreamStatus("disconnected");
        setLastError("WS 鉴权失败，请重新登录。");
        return;
      }
      if (event.code === 4403) {
        setStreamStatus("disconnected");
        setLastError("WS Origin 校验失败，请检查前端域名与后端配置。");
        return;
      }

      setDegradedMode("reconnecting");

      reconnectAttemptRef.current += 1;
      const backoff = Math.min(
        RECONNECT_MAX_DELAY_MS,
        Math.round(1000 * Math.pow(2, reconnectAttemptRef.current - 1))
      );

      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      reconnectTimerRef.current = window.setTimeout(() => {
        connectStream();
      }, backoff);
    };
  }, [handleStreamMessage, setDegradedMode, stopDegradedPolling, syncSubscriptions]);

  const closeStream = React.useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    stopDegradedPolling();

    const ws = wsRef.current;
    if (ws) {
      wsRef.current = null;
      ws.close();
    }

    subscriptionSetRef.current = new Set();
  }, [stopDegradedPolling]);

  const desiredSubscriptions = React.useMemo(() => {
    const set = new Set<string>();

    watchlist.forEach((item) => {
      const symbol = normalizeSymbol(item.ticker);
      if (symbol) set.add(symbol);
    });
    return [...set];
  }, [watchlist]);

  React.useEffect(() => {
    desiredSubscriptionsRef.current = desiredSubscriptions;
    syncSubscriptions();
  }, [desiredSubscriptions, syncSubscriptions]);

  React.useEffect(() => {
    void refreshWatchlist();
  }, [refreshWatchlist]);

  React.useEffect(() => {
    if (!token) {
      manualCloseRef.current = true;
      closeStream();
      setStreamStatus("idle");
      setStreamSource("REST");
      setDataLatency("delayed");
      return;
    }

    manualCloseRef.current = false;
    connectStream();

    return () => {
      manualCloseRef.current = true;
      closeStream();
    };
  }, [closeStream, connectStream, token]);

  React.useEffect(() => {
    if (!watchlist.length || !token) {
      return;
    }
    void refreshSnapshots(watchlist.map((item) => item.ticker));
  }, [refreshSnapshots, token, watchlist]);

  React.useEffect(() => {
    if (!activeTicker) {
      return;
    }

    void loadTickerDetail(activeTicker, true);
  }, [activeTicker, loadTickerDetail]);

  const activeDetail = activeTicker ? detailsByTicker[activeTicker] : null;
  const activeSnapshot = activeTicker ? snapshotMap[activeTicker] : null;
  const latestBar = activeDetail?.bars.at(-1);

  const onAddTicker = React.useCallback(async () => {
    if (!token) return;

    const symbol = normalizeSymbol(tickerInput);
    if (!symbol) return;
    if (!/^[A-Z.]{1,15}$/.test(symbol)) {
      setWatchlistError("Ticker format is invalid.");
      return;
    }

    setWatchlistError(null);
    try {
      await addWatchlist(token, symbol);
      setTickerInput("");
      await refreshWatchlist();
      setActiveTicker(symbol);
      await refreshSnapshots([symbol]);
      void loadTickerDetail(symbol, true);
    } catch (error: any) {
      setWatchlistError(error?.message ?? "Failed to add ticker.");
    }
  }, [loadTickerDetail, refreshSnapshots, refreshWatchlist, tickerInput, token]);

  const onDeleteTicker = React.useCallback(
    async (ticker: string) => {
      if (!token) return;

      const symbol = normalizeSymbol(ticker);
      setWatchlistError(null);

      try {
        await deleteWatchlist(token, symbol);
        await refreshWatchlist();
      } catch (error: any) {
        setWatchlistError(error?.message ?? "Failed to delete ticker.");
      }
    },
    [refreshWatchlist, token]
  );

  const onSelectTicker = React.useCallback(
    (ticker: string) => {
      const symbol = normalizeSymbol(ticker);
      setActiveTicker(symbol);
      void loadTickerDetail(symbol);
    },
    [loadTickerDetail]
  );

  return {
    userEmail: user?.email ?? null,
    isAuthenticated: Boolean(token),
    watchlist,
    watchlistBusy,
    watchlistError,
    tickerInput,
    setTickerInput,
    refreshWatchlist,
    onAddTicker,
    onDeleteTicker,
    onSelectTicker,

    activeTicker,
    snapshotMap,
    timeframe,
    setTimeframe,
    activeDetail,
    activeSnapshot,
    latestBar,
    loadTickerDetail,
    refreshSnapshots,

    streamStatus,
    streamSource,
    dataLatency,
    lastSyncAt,
    lastError
  };
}

function dateOffset(days: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function marketQueryForTimeframe(timeframe: TimeframeKey): {
  timespan: string;
  multiplier: number;
  fromDays: number;
  limit: number;
} {
  switch (timeframe) {
    case "5m":
      return { timespan: "minute", multiplier: 5, fromDays: -14, limit: 2500 };
    case "15m":
      return { timespan: "minute", multiplier: 15, fromDays: -14, limit: 1200 };
    case "60m":
      return { timespan: "minute", multiplier: 60, fromDays: -14, limit: 520 };
    case "week":
      return { timespan: "week", multiplier: 1, fromDays: -3650, limit: 700 };
    case "month":
      return { timespan: "month", multiplier: 1, fromDays: -7300, limit: 360 };
    case "day":
    default:
      return { timespan: "day", multiplier: 1, fromDays: -320, limit: 900 };
  }
}

function normalizeSymbol(value: string | null | undefined): string {
  return (value ?? "").trim().toUpperCase();
}

function chunkSymbols(symbols: string[], size: number): string[][] {
  if (size <= 0) return [symbols];
  const chunks: string[][] = [];
  for (let index = 0; index < symbols.length; index += size) {
    chunks.push(symbols.slice(index, index + size));
  }
  return chunks;
}

function createEmptySnapshot(symbol: string): MarketSnapshot {
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

function buildStreamUrl(token: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const params = new URLSearchParams({ token });
  return `${protocol}//${window.location.host}/api/v1/market-data/stream?${params.toString()}`;
}

function toMillis(value: string): number {
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function resolveSnapshotLast(currentLast: number, message: StreamMarketMessage): number {
  if (message.type === "market.trade") {
    return message.last ?? message.price ?? currentLast;
  }
  if (message.type === "market.aggregate") {
    return message.last ?? message.close ?? currentLast;
  }
  return currentLast;
}
