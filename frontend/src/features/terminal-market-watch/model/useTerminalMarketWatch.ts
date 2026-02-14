import React from "react";

import {
  buildIndicators,
  listMarketBars,
  listMarketSnapshots,
  type MarketBar,
  type MarketSnapshot
} from "@/entities/market";
import {
  getOptionContract,
  listOptionChain,
  listOptionExpirations,
  type OptionChainItem,
  type OptionContract
} from "@/entities/options";
import { useSession } from "@/entities/session";
import { addWatchlist, deleteWatchlist, listWatchlist, type WatchlistItem } from "@/entities/watchlist";

import {
  type DetailSnapshot,
  type OptionTypeFilter,
  type StreamStatus,
  type TimeframeKey,
  type TimeframeOption,
  type TerminalMarketWatchViewModel
} from "./types";

export const TIMEFRAME_OPTIONS: TimeframeOption[] = [
  { key: "minute", label: "Minute" },
  { key: "day", label: "Day" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" }
];

const STREAM_CHANNELS = ["trade", "quote", "aggregate"];
const STREAM_DEGRADED_THRESHOLD_MS = 10_000;
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

  const [expirations, setExpirations] = React.useState<Array<{ date: string; days_to_expiration: number }>>([]);
  const [expirationsBusy, setExpirationsBusy] = React.useState(false);
  const [expirationsError, setExpirationsError] = React.useState<string | null>(null);
  const [selectedExpiration, setSelectedExpiration] = React.useState<string | null>(null);

  const [optionTypeFilter, setOptionTypeFilter] = React.useState<OptionTypeFilter>("all");
  const [optionChain, setOptionChain] = React.useState<OptionChainItem[]>([]);
  const [chainBusy, setChainBusy] = React.useState(false);
  const [chainError, setChainError] = React.useState<string | null>(null);

  const [selectedContractTicker, setSelectedContractTicker] = React.useState<string | null>(null);
  const [contractDetail, setContractDetail] = React.useState<OptionContract | null>(null);
  const [contractBusy, setContractBusy] = React.useState(false);
  const [contractError, setContractError] = React.useState<string | null>(null);

  const activeTickerRef = React.useRef<string | null>(null);
  const selectedContractTickerRef = React.useRef<string | null>(null);
  const tokenRef = React.useRef<string | null>(null);
  const desiredSubscriptionsRef = React.useRef<string[]>([]);

  const refreshSnapshotsRef = React.useRef<(symbols?: string[]) => Promise<void>>(async () => undefined);
  const loadTickerDetailRef = React.useRef<(ticker: string, force?: boolean) => Promise<void>>(async () => undefined);

  const wsRef = React.useRef<WebSocket | null>(null);
  const reconnectAttemptRef = React.useRef(0);
  const reconnectingSinceRef = React.useRef<number | null>(null);
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
    selectedContractTickerRef.current = selectedContractTicker;
  }, [selectedContractTicker]);

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

  const applyStreamSnapshot = React.useCallback((symbol: string, payload: Record<string, unknown>, eventAt: string) => {
    const incomingTs = toMillis(eventAt);
    const knownTs = snapshotTsRef.current[symbol] ?? 0;
    if (incomingTs < knownTs) {
      return;
    }

    snapshotTsRef.current[symbol] = incomingTs;

    setSnapshotMap((previous) => {
      const base = previous[symbol] ?? createEmptySnapshot(symbol);

      return {
        ...previous,
        [symbol]: {
          ...base,
          last: asNumber(payload.last) ?? asNumber(payload.price) ?? base.last,
          change: asNumber(payload.change) ?? base.change,
          change_pct: asNumber(payload.change_pct) ?? base.change_pct,
          open: asNumber(payload.open) ?? base.open,
          high: asNumber(payload.high) ?? base.high,
          low: asNumber(payload.low) ?? base.low,
          volume: asNumber(payload.volume) ?? base.volume,
          market_status: asString(payload.market_status) ?? base.market_status,
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
    setStreamSource("WS");
    setDataLatency("real-time");
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
          source: previous[symbol]?.source ?? null
        }
      }));

      try {
        const query = marketQueryForTimeframe(timeframe);
        const bars = await listMarketBars({
          token,
          ticker: symbol,
          timespan: query.timespan,
          multiplier: query.multiplier,
          from: dateOffset(query.fromDays),
          to: dateOffset(0),
          limit: query.limit
        });

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
            source: "REST"
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
            source: previous[symbol]?.source ?? null
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

  const handleStreamMessage = React.useCallback(
    (raw: string) => {
      const payload = safeJsonParse(raw);
      if (!payload) return;

      const messageType = asString(payload.type);
      const messageData = asRecord(payload.data) ?? {};

      if (messageType === "system.ping") {
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ action: "ping" }));
        }
        return;
      }

      if (messageType === "system.status") {
        const latencyValue = asString(messageData.latency)?.toLowerCase();
        if (latencyValue === "real-time" || latencyValue === "delayed") {
          setDataLatency(latencyValue);
        }
        return;
      }

      if (messageType === "system.error") {
        const code = asString(messageData.code);
        const message = asString(messageData.message) ?? "stream error";
        setLastError(code ? `${code}: ${message}` : message);

        if (code === "STREAM_SUBSCRIPTION_LIMIT_EXCEEDED") {
          setContractError("已达 WS 订阅上限，当前合约仅展示 REST 数据。");
        }

        return;
      }

      if (!messageType?.startsWith("market.")) {
        return;
      }

      const symbol = normalizeSymbol(asString(messageData.symbol));
      if (!symbol) return;

      const eventAt = asString(messageData.event_ts) ?? asString(payload.ts) ?? new Date().toISOString();
      applyStreamSnapshot(symbol, messageData, eventAt);

      if (symbol === selectedContractTickerRef.current) {
        setContractDetail((previous) => {
          if (!previous) return previous;
          return {
            ...previous,
            quote: {
              ...previous.quote,
              bid: asNumber(messageData.bid) ?? previous.quote.bid,
              ask: asNumber(messageData.ask) ?? previous.quote.ask,
              last: asNumber(messageData.last) ?? previous.quote.last,
              updated_at: eventAt
            },
            source: "WS"
          };
        });
      }
    },
    [applyStreamSnapshot]
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
      reconnectingSinceRef.current = null;

      stopDegradedPolling();
      setStreamStatus("connected");
      setStreamSource("WS");
      setDataLatency("real-time");
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

      if (!reconnectingSinceRef.current) {
        reconnectingSinceRef.current = Date.now();
      }

      const reconnectDuration = Date.now() - reconnectingSinceRef.current;
      if (reconnectDuration >= STREAM_DEGRADED_THRESHOLD_MS) {
        setStreamStatus("degraded");
        setStreamSource("REST");
        setDataLatency("delayed");
        startDegradedPolling();
      } else {
        setStreamStatus("reconnecting");
        setDataLatency("delayed");
      }

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
  }, [handleStreamMessage, startDegradedPolling, stopDegradedPolling, syncSubscriptions]);

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

  const loadExpirations = React.useCallback(
    async (underlying: string) => {
      if (!token) return;

      setExpirationsBusy(true);
      setExpirationsError(null);

      try {
        const payload = await listOptionExpirations(token, underlying);
        const records = payload.expirations.map((item) => ({
          date: item.date,
          days_to_expiration: item.days_to_expiration
        }));

        setExpirations(records);
        setSelectedExpiration((previous) => {
          if (previous && records.some((item) => item.date === previous)) {
            return previous;
          }
          return records[0]?.date ?? null;
        });
      } catch (error: any) {
        setExpirations([]);
        setSelectedExpiration(null);
        setExpirationsError(error?.message ?? "Failed to load expirations.");
      } finally {
        setExpirationsBusy(false);
      }
    },
    [token]
  );

  const loadOptionChainData = React.useCallback(
    async (underlying: string, expiration: string) => {
      if (!token) return;

      setChainBusy(true);
      setChainError(null);

      try {
        const payload = await listOptionChain({
          token,
          underlying,
          expiration,
          option_type: optionTypeFilter,
          limit: 200
        });

        setOptionChain(payload.items);
      } catch (error: any) {
        setOptionChain([]);
        setChainError(error?.message ?? "Failed to load option chain.");
      } finally {
        setChainBusy(false);
      }
    },
    [optionTypeFilter, token]
  );

  const loadContractDetail = React.useCallback(
    async (optionTicker: string) => {
      if (!token) return;

      setContractBusy(true);
      setContractError(null);

      try {
        const contract = await getOptionContract(token, optionTicker);
        setContractDetail(contract);
      } catch (error: any) {
        setContractDetail(null);
        setContractError(error?.message ?? `Failed to load ${optionTicker}`);
      } finally {
        setContractBusy(false);
      }
    },
    [token]
  );

  const desiredSubscriptions = React.useMemo(() => {
    const set = new Set<string>();

    watchlist.forEach((item) => {
      const symbol = normalizeSymbol(item.ticker);
      if (symbol) set.add(symbol);
    });

    if (selectedContractTicker) {
      set.add(normalizeSymbol(selectedContractTicker));
    }

    return [...set];
  }, [selectedContractTicker, watchlist]);

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
      setOptionChain([]);
      setExpirations([]);
      setSelectedExpiration(null);
      setContractDetail(null);
      setSelectedContractTicker(null);
      return;
    }

    void loadTickerDetail(activeTicker, true);
    void loadExpirations(activeTicker);
  }, [activeTicker, loadExpirations, loadTickerDetail]);

  React.useEffect(() => {
    if (!activeTicker || !selectedExpiration) {
      setOptionChain([]);
      return;
    }

    void loadOptionChainData(activeTicker, selectedExpiration);
  }, [activeTicker, loadOptionChainData, selectedExpiration]);

  React.useEffect(() => {
    if (!selectedContractTicker) {
      setContractDetail(null);
      return;
    }

    void loadContractDetail(selectedContractTicker);
  }, [loadContractDetail, selectedContractTicker]);

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
        setSelectedContractTicker((current) =>
          optionTickerBelongsToUnderlying(current, symbol) ? null : current
        );
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
    lastError,

    expirations,
    expirationsBusy,
    expirationsError,
    selectedExpiration,
    setSelectedExpiration,

    optionTypeFilter,
    setOptionTypeFilter,
    optionChain,
    chainBusy,
    chainError,

    selectedContractTicker,
    setSelectedContractTicker,
    contractDetail,
    contractBusy,
    contractError,

    loadExpirations,
    loadOptionChainData
  };
}

function dateOffset(days: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function marketQueryForTimeframe(timeframe: TimeframeKey): {
  timespan: string;
  multiplier: number;
  fromDays: number;
  limit: number;
} {
  switch (timeframe) {
    case "minute":
      return { timespan: "minute", multiplier: 1, fromDays: -3, limit: 4500 };
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

function optionTickerBelongsToUnderlying(optionTicker: string | null, underlying: string): boolean {
  if (!optionTicker) return false;
  const normalizedTicker = normalizeSymbol(optionTicker);
  const normalizedUnderlying = normalizeSymbol(underlying);
  return normalizedTicker.startsWith(`O:${normalizedUnderlying}`);
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

function safeJsonParse(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    if (parsed && typeof parsed === "object") {
      return parsed as Record<string, unknown>;
    }
    return null;
  } catch {
    return null;
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object") {
    return value as Record<string, unknown>;
  }
  return null;
}

function asString(value: unknown): string | null {
  if (typeof value === "string") return value;
  return null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}
