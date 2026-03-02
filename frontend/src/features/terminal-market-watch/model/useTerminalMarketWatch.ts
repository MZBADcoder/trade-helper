import React from "react";

import {
  buildIndicators,
  listMarketBarsWithMeta,
  listMarketSnapshots,
  type MarketBar,
  type MarketSnapshot
} from "@/entities/market";
import { useSession } from "@/entities/session";
import { addWatchlist, deleteWatchlist, listWatchlist, type WatchlistItem } from "@/entities/watchlist";

import {
  type DetailSnapshot,
  type SessionKey,
  type StreamStatus,
  type TimeframeKey,
  type TerminalMarketWatchViewModel
} from "./types";
import {
  TIMEFRAME_OPTIONS,
  type DateRange,
  buildDetailCacheKey,
  buildStreamUrl,
  chunkSymbols,
  compareDateString,
  createEmptySnapshot,
  currentMarketDate,
  dateOffset,
  isDetailKeyForSymbol,
  isIntradayTimeframe,
  isMarketStreamWindowOpen,
  marketQueryForTimeframe,
  mergeBarsByStartAt,
  normalizeSymbol,
  previousHistoryDate,
  resolveFetchRange,
  resolveMarketRealtimeConfig,
  resolveSnapshotLast,
  sessionKeyForTimeframe,
  resolveTradingChunkFetchRange,
  resolveTradingFetchRange,
  shouldIgnoreMarketMessage,
  shouldStopDegradedPollingOnStatus,
  sortBars,
  streamChannelsForRealtime,
  toMillis
} from "./marketWatchUtils";
import { parseStreamEnvelope, type StreamMarketMessage, type StreamStatusMessage } from "./streamProtocol";
const SNAPSHOT_POLL_INTERVAL_MS = 4_000;
const BARS_POLL_INTERVAL_MS = 20_000;
const MARKET_STATUS_POLL_INTERVAL_MS = 60_000;
const MARKET_CLOCK_TICK_MS = 30_000;
const RECONNECT_MAX_DELAY_MS = 10_000;

const DETAIL_CACHE_MAX_ENTRIES = 12;
const DETAIL_CACHE_MAX_TOTAL_BARS = 36_000;

const MARKET_REALTIME_CONFIG = resolveMarketRealtimeConfig({
  delayMinutes: import.meta.env.VITE_MARKET_DELAY_MINUTES
});

export function useTerminalMarketWatch(): TerminalMarketWatchViewModel {
  const { token, user } = useSession();
  const { delayMinutes } = MARKET_REALTIME_CONFIG;
  const streamChannels = React.useMemo(() => streamChannelsForRealtime(), []);

  const [watchlist, setWatchlist] = React.useState<WatchlistItem[]>([]);
  const [watchlistBusy, setWatchlistBusy] = React.useState(false);
  const [watchlistError, setWatchlistError] = React.useState<string | null>(null);
  const [tickerInput, setTickerInput] = React.useState("");

  const [activeTicker, setActiveTicker] = React.useState<string | null>(null);
  const [timeframe, setTimeframe] = React.useState<TimeframeKey>("day");
  const [session, setSession] = React.useState<SessionKey>("regular");
  const [detailsByKey, setDetailsByKey] = React.useState<Record<string, DetailSnapshot>>({});
  const detailsRef = React.useRef<Record<string, DetailSnapshot>>({});
  const detailLruRef = React.useRef<string[]>([]);
  const loadMoreInFlightRef = React.useRef<Set<string>>(new Set());
  const detailRequestVersionRef = React.useRef<Record<string, number>>({});

  const [snapshotMap, setSnapshotMap] = React.useState<Record<string, MarketSnapshot>>({});
  const snapshotTsRef = React.useRef<Record<string, number>>({});

  const [streamStatus, setStreamStatus] = React.useState<StreamStatus>("idle");
  const [streamSource, setStreamSource] = React.useState<"WS" | "REST">("REST");
  const [dataLatency, setDataLatency] = React.useState<"real-time" | "delayed">("delayed");
  const [lastSyncAt, setLastSyncAt] = React.useState<string | null>(null);
  const [lastError, setLastError] = React.useState<string | null>(null);
  const [marketClockMs, setMarketClockMs] = React.useState(() => Date.now());

  const activeTickerRef = React.useRef<string | null>(null);
  const timeframeRef = React.useRef<TimeframeKey>(timeframe);
  const sessionRef = React.useRef<SessionKey>(session);
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
  const closingSocketSetRef = React.useRef<WeakSet<WebSocket>>(new WeakSet());
  const subscriptionSetRef = React.useRef<Set<string>>(new Set());

  React.useEffect(() => {
    detailsRef.current = detailsByKey;
  }, [detailsByKey]);

  React.useEffect(() => {
    activeTickerRef.current = activeTicker;
  }, [activeTicker]);

  React.useEffect(() => {
    timeframeRef.current = timeframe;
  }, [timeframe]);

  React.useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  React.useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  React.useEffect(() => {
    const timer = window.setInterval(() => {
      setMarketClockMs(Date.now());
    }, MARKET_CLOCK_TICK_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, []);

  const trimDetailCache = React.useCallback(
    (cache: Record<string, DetailSnapshot>, touchedKey?: string): Record<string, DetailSnapshot> => {
      let nextOrder = detailLruRef.current.filter((key) => cache[key] !== undefined);
      if (touchedKey) {
        nextOrder = nextOrder.filter((key) => key !== touchedKey);
        nextOrder.push(touchedKey);
      }

      const nextCache = { ...cache };
      const totalBars = () =>
        Object.values(nextCache).reduce((sum, detail) => sum + detail.bars.length, 0);

      let rotateGuard = 0;
      while (
        (nextOrder.length > DETAIL_CACHE_MAX_ENTRIES || totalBars() > DETAIL_CACHE_MAX_TOTAL_BARS) &&
        nextOrder.length > 0
      ) {
        const oldest = nextOrder[0];
        if (oldest === touchedKey && nextOrder.length > 1) {
          nextOrder.push(nextOrder.shift() as string);
          rotateGuard += 1;
          if (rotateGuard > nextOrder.length * 2) break;
          continue;
        }

        delete nextCache[oldest];
        nextOrder.shift();
      }

      detailLruRef.current = nextOrder;
      return nextCache;
    },
    []
  );

  const touchDetailKey = React.useCallback((key: string) => {
    detailLruRef.current = detailLruRef.current.filter((item) => item !== key);
    detailLruRef.current.push(key);
  }, []);

  const upsertDetail = React.useCallback(
    (
      key: string,
      updater: (current: DetailSnapshot | undefined) => DetailSnapshot,
      touch = true
    ) => {
      setDetailsByKey((previous) => {
        const next = {
          ...previous,
          [key]: updater(previous[key])
        };
        return trimDetailCache(next, touch ? key : undefined);
      });
    },
    [trimDetailCache]
  );

  const removeDetailsBySymbol = React.useCallback((symbol: string) => {
    setDetailsByKey((previous) => {
      const next: Record<string, DetailSnapshot> = {};
      Object.entries(previous).forEach(([key, detail]) => {
        if (!isDetailKeyForSymbol(key, symbol)) {
          next[key] = detail;
        }
      });
      detailLruRef.current = detailLruRef.current.filter((key) => next[key] !== undefined);
      Object.keys(detailRequestVersionRef.current).forEach((key) => {
        if (isDetailKeyForSymbol(key, symbol)) {
          delete detailRequestVersionRef.current[key];
        }
      });
      return next;
    });
  }, []);

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

  const applyStreamMarketMessage = React.useCallback(
    (message: StreamMarketMessage) => {
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

      setDetailsByKey((previous) => {
        let changed = false;
        const next = { ...previous };

        Object.entries(previous).forEach(([key, detail]) => {
          if (!isDetailKeyForSymbol(key, symbol)) return;
          changed = true;
          next[key] = {
            ...detail,
            updatedAt: eventAt,
            source: "WS"
          };
        });

        if (!changed) return previous;
        return trimDetailCache(next);
      });

      setLastSyncAt(eventAt);
    },
    [trimDetailCache]
  );

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
      const activeTimeframe = timeframeRef.current;
      const activeSession = sessionRef.current;
      const resolvedSession = sessionKeyForTimeframe(activeTimeframe, activeSession);
      const cacheKey = buildDetailCacheKey(symbol, activeTimeframe, resolvedSession);
      const query = marketQueryForTimeframe(activeTimeframe);
      const existing = detailsRef.current[cacheKey];
      const requestVersion = (detailRequestVersionRef.current[cacheKey] ?? 0) + 1;
      detailRequestVersionRef.current[cacheKey] = requestVersion;
      const isStaleRequest = () => detailRequestVersionRef.current[cacheKey] !== requestVersion;

      if (!force && existing?.bars.length) {
        touchDetailKey(cacheKey);
        return;
      }

      upsertDetail(
        cacheKey,
        (previous) => ({
          bars: previous?.bars ?? [],
          indicators: previous?.indicators ?? null,
          timeframe: activeTimeframe,
          loading: true,
          loadingMoreBefore: previous?.loadingMoreBefore ?? false,
          hasMoreBefore: previous?.hasMoreBefore ?? false,
          earliestLoadedAt: previous?.earliestLoadedAt ?? null,
          lookbackStartDate: previous?.lookbackStartDate ?? null,
          nextFetchEndDate: previous?.nextFetchEndDate ?? null,
          error: null,
          updatedAt: previous?.updatedAt ?? null,
          source: previous?.source ?? null,
          barsDataSource: previous?.barsDataSource ?? null
        })
      );

      const endDate = query.useTradingDays ? currentMarketDate() : dateOffset(0);
      const windowDays = force && existing?.bars.length ? query.refreshWindowDays : query.initialWindowDays;
      const defaultLookbackStartDate = dateOffset(-(query.lookbackDays - 1));
      let lookbackStartDate = defaultLookbackStartDate;
      let range: DateRange = resolveFetchRange({
        lookbackStartDate: defaultLookbackStartDate,
        endDate,
        windowDays
      });
      let previousTradingDate: string | null = null;
      if (query.useTradingDays) {
        const tradingRange = await resolveTradingFetchRange({
          token,
          lookbackDays: query.lookbackDays,
          endDate,
          windowDays
        });
        if (isStaleRequest()) {
          return;
        }
        lookbackStartDate = tradingRange.lookbackStartDate;
        range = tradingRange;
        previousTradingDate = tradingRange.previousTradingDate;
      }

      try {
        const payload = await listMarketBarsWithMeta({
          token,
          ticker: symbol,
          timespan: query.timespan,
          multiplier: query.multiplier,
          session: resolvedSession,
          from: range.from,
          to: range.to,
          limit: query.limit
        });
        if (isStaleRequest()) {
          return;
        }

        const incomingBars = sortBars(payload.items);

        upsertDetail(cacheKey, (previous) => {
          const baseBars =
            force && (previous?.bars.length || existing?.bars.length)
              ? previous?.bars ?? existing?.bars ?? []
              : [];
          const mergedBars =
            force && baseBars.length > 0
              ? mergeBarsByStartAt(baseBars, incomingBars)
              : incomingBars;
          const persistedLookbackStartDate =
            previous?.lookbackStartDate ?? existing?.lookbackStartDate ?? lookbackStartDate;
          const nextFetchEndDate =
            force && (previous?.bars.length || existing?.bars.length)
              ? previous?.nextFetchEndDate ?? existing?.nextFetchEndDate ?? null
              : query.useTradingDays
                ? (previousTradingDate ?? previousHistoryDate(range.from))
                : previousHistoryDate(range.from);
          const hasMoreBefore = Boolean(
            mergedBars.length > 0 &&
              nextFetchEndDate &&
              compareDateString(nextFetchEndDate, persistedLookbackStartDate) >= 0
          );

          return {
            bars: mergedBars,
            indicators: buildIndicators(mergedBars),
            timeframe: activeTimeframe,
            loading: false,
            loadingMoreBefore: false,
            hasMoreBefore,
            earliestLoadedAt: mergedBars[0]?.start_at ?? null,
            lookbackStartDate: persistedLookbackStartDate,
            nextFetchEndDate,
            error: null,
            updatedAt: new Date().toISOString(),
            source: "REST",
            barsDataSource: payload.dataSource
          };
        });
      } catch (error: any) {
        if (isStaleRequest()) {
          return;
        }
        upsertDetail(cacheKey, (previous) => ({
          bars: previous?.bars ?? [],
          indicators: previous?.indicators ?? null,
          timeframe: activeTimeframe,
          loading: false,
          loadingMoreBefore: previous?.loadingMoreBefore ?? false,
          hasMoreBefore: previous?.hasMoreBefore ?? false,
          earliestLoadedAt: previous?.earliestLoadedAt ?? null,
          lookbackStartDate: previous?.lookbackStartDate ?? lookbackStartDate,
          nextFetchEndDate: previous?.nextFetchEndDate ?? null,
          error: error?.message ?? `Failed to load ${symbol}`,
          updatedAt: previous?.updatedAt ?? null,
          source: previous?.source ?? null,
          barsDataSource: previous?.barsDataSource ?? null
        }));
      }
    },
    [token, touchDetailKey, upsertDetail]
  );

  const loadMoreTickerHistory = React.useCallback(
    async (ticker: string) => {
      if (!token) return;

      const symbol = normalizeSymbol(ticker);
      const activeTimeframe = timeframeRef.current;
      const activeSession = sessionRef.current;
      const resolvedSession = sessionKeyForTimeframe(activeTimeframe, activeSession);
      if (!isIntradayTimeframe(activeTimeframe)) {
        return;
      }

      const cacheKey = buildDetailCacheKey(symbol, activeTimeframe, resolvedSession);
      const existing = detailsRef.current[cacheKey];
      const query = marketQueryForTimeframe(activeTimeframe);

      if (!existing || existing.loading || existing.loadingMoreBefore) return;
      if (!existing.hasMoreBefore || !existing.nextFetchEndDate || !existing.lookbackStartDate) return;
      if (loadMoreInFlightRef.current.has(cacheKey)) return;
      const lookbackStartDate = existing.lookbackStartDate;

      loadMoreInFlightRef.current.add(cacheKey);
      upsertDetail(cacheKey, (previous) => ({
        bars: previous?.bars ?? [],
        indicators: previous?.indicators ?? null,
        timeframe: activeTimeframe,
        loading: false,
        loadingMoreBefore: true,
        hasMoreBefore: previous?.hasMoreBefore ?? false,
        earliestLoadedAt: previous?.earliestLoadedAt ?? null,
        lookbackStartDate: previous?.lookbackStartDate ?? existing.lookbackStartDate,
        nextFetchEndDate: previous?.nextFetchEndDate ?? existing.nextFetchEndDate,
        error: null,
        updatedAt: previous?.updatedAt ?? null,
        source: previous?.source ?? null,
        barsDataSource: previous?.barsDataSource ?? null
      }));

      let range: DateRange = resolveFetchRange({
        lookbackStartDate: existing.lookbackStartDate,
        endDate: existing.nextFetchEndDate,
        windowDays: query.chunkWindowDays
      });
      let previousTradingDate: string | null = null;
      if (query.useTradingDays) {
        const tradingRange = await resolveTradingChunkFetchRange({
          token,
          lookbackStartDate: existing.lookbackStartDate,
          endDate: existing.nextFetchEndDate,
          windowDays: query.chunkWindowDays
        });
        range = tradingRange;
        previousTradingDate = tradingRange.previousTradingDate;
      }

      try {
        const payload = await listMarketBarsWithMeta({
          token,
          ticker: symbol,
          timespan: query.timespan,
          multiplier: query.multiplier,
          session: resolvedSession,
          from: range.from,
          to: range.to,
          limit: query.limit
        });

        const incomingBars = sortBars(payload.items);
        const nextFetchEndDate = query.useTradingDays
          ? (previousTradingDate ?? previousHistoryDate(range.from))
          : previousHistoryDate(range.from);

        upsertDetail(cacheKey, (previous) => {
          const currentBars = previous?.bars ?? existing.bars;
          const mergedBars = mergeBarsByStartAt(currentBars, incomingBars);
          const persistedLookbackStartDate = previous?.lookbackStartDate ?? lookbackStartDate;
          const hasMoreBefore =
            compareDateString(nextFetchEndDate, persistedLookbackStartDate) >= 0;

          return {
            bars: mergedBars,
            indicators: buildIndicators(mergedBars),
            timeframe: activeTimeframe,
            loading: false,
            loadingMoreBefore: false,
            hasMoreBefore,
            earliestLoadedAt: mergedBars[0]?.start_at ?? existing.earliestLoadedAt,
            lookbackStartDate: persistedLookbackStartDate,
            nextFetchEndDate,
            error: null,
            updatedAt: new Date().toISOString(),
            source: "REST",
            barsDataSource: payload.dataSource ?? previous?.barsDataSource ?? existing.barsDataSource
          };
        });
      } catch (error: any) {
        upsertDetail(cacheKey, (previous) => ({
          bars: previous?.bars ?? existing.bars,
          indicators: previous?.indicators ?? existing.indicators,
          timeframe: activeTimeframe,
          loading: false,
          loadingMoreBefore: false,
          hasMoreBefore: previous?.hasMoreBefore ?? existing.hasMoreBefore,
          earliestLoadedAt: previous?.earliestLoadedAt ?? existing.earliestLoadedAt,
          lookbackStartDate: previous?.lookbackStartDate ?? lookbackStartDate,
          nextFetchEndDate: previous?.nextFetchEndDate ?? existing.nextFetchEndDate,
          error: error?.message ?? `Failed to load older ${symbol} bars`,
          updatedAt: previous?.updatedAt ?? existing.updatedAt,
          source: previous?.source ?? existing.source,
          barsDataSource: previous?.barsDataSource ?? existing.barsDataSource
        }));
      } finally {
        loadMoreInFlightRef.current.delete(cacheKey);
      }
    },
    [token, upsertDetail]
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
        if (!isIntradayTimeframe(timeframeRef.current)) return;
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
            channels: streamChannels
          })
        );
      }

      if (toSubscribe.length) {
        ws.send(
          JSON.stringify({
            action: "subscribe",
            symbols: toSubscribe,
            channels: streamChannels
          })
        );
      }

      subscriptionSetRef.current = desiredSet;
    } catch {
      setLastError("订阅更新失败，等待连接恢复后重试。");
    }
  }, [streamChannels]);

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
      setDataLatency(message.latency ?? "delayed");

      if (shouldStopDegradedPollingOnStatus(message)) {
        stopDegradedPolling();
        setStreamStatus("connected");
        setStreamSource("WS");
        setDataLatency(message.latency ?? "delayed");
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

      if (shouldIgnoreMarketMessage(message)) {
        return;
      }

      applyStreamMarketMessage(message);
    },
    [applyStreamMarketMessage, applySystemStatus, setDegradedMode]
  );

  const connectStream = React.useCallback(() => {
    if (!tokenRef.current) return;

    const current = wsRef.current;
    if (current && (current.readyState === WebSocket.OPEN || current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setStreamStatus((previous) =>
      previous === "idle" || previous === "disconnected" ? "connecting" : "reconnecting"
    );

    const ws = new WebSocket(buildStreamUrl());
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
      const closedByCleanup = closingSocketSetRef.current.has(ws);
      if (closedByCleanup) {
        closingSocketSetRef.current.delete(ws);
      }

      if (closedByCleanup || manualCloseRef.current || !tokenRef.current) {
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
      if (event.code === 4409) {
        setStreamStatus("disconnected");
        setLastError("当前为非交易时段（按延迟窗口），WS 已关闭。");
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
      closingSocketSetRef.current.add(ws);
      ws.close(1000, "client_cleanup");
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

  const isTradingSessionOpen = React.useMemo(() => {
    if (!watchlist.length) {
      return false;
    }
    return isMarketStreamWindowOpen({
      delayMinutes,
      nowMs: marketClockMs
    });
  }, [delayMinutes, marketClockMs, watchlist.length]);

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

    if (!watchlist.length) {
      manualCloseRef.current = true;
      closeStream();
      setStreamStatus("idle");
      setStreamSource("REST");
      setDataLatency("delayed");
      return;
    }

    if (!isTradingSessionOpen) {
      manualCloseRef.current = true;
      closeStream();
      setStreamStatus("disconnected");
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
  }, [closeStream, connectStream, isTradingSessionOpen, token, watchlist.length]);

  React.useEffect(() => {
    if (!watchlist.length || !token) {
      return;
    }
    void refreshSnapshots(watchlist.map((item) => item.ticker));
  }, [refreshSnapshots, token, watchlist]);

  const activeSessionKey = React.useMemo(
    () => sessionKeyForTimeframe(timeframe, session),
    [timeframe, session]
  );

  React.useEffect(() => {
    if (!watchlist.length || !token) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshSnapshotsRef.current();
    }, MARKET_STATUS_POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [token, watchlist.length]);

  React.useEffect(() => {
    if (!activeTicker) {
      return;
    }

    void loadTickerDetail(activeTicker, true);
  }, [activeTicker, activeSessionKey, loadTickerDetail, timeframe]);

  React.useEffect(() => {
    if (!activeTicker) return;
    touchDetailKey(buildDetailCacheKey(activeTicker, timeframe, activeSessionKey));
  }, [activeTicker, activeSessionKey, timeframe, touchDetailKey]);

  const activeDetailKey = activeTicker ? buildDetailCacheKey(activeTicker, timeframe, activeSessionKey) : null;
  const activeDetail = activeDetailKey ? detailsByKey[activeDetailKey] ?? null : null;
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
        removeDetailsBySymbol(symbol);
        setSnapshotMap((previous) => {
          const next = { ...previous };
          delete next[symbol];
          return next;
        });
        delete snapshotTsRef.current[symbol];
        await refreshWatchlist();
      } catch (error: any) {
        setWatchlistError(error?.message ?? "Failed to delete ticker.");
      }
    },
    [refreshWatchlist, removeDetailsBySymbol, token]
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
    session,
    setSession,
    activeDetail,
    activeSnapshot,
    latestBar,
    loadTickerDetail,
    loadMoreTickerHistory,
    refreshSnapshots,

    streamStatus,
    streamSource,
    dataLatency,
    delayMinutes,
    lastSyncAt,
    lastError
  };
}
