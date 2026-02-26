import React from "react";

import { buildIndicators, type IndicatorBundle, type MarketBar } from "@/entities/market";
import { type WatchlistItem } from "@/entities/watchlist";

import {
  buildDemoBars,
  defaultDemoDataEnvironment,
  type DemoDataEnvironment,
  type DemoStorage,
  loadDemoWatchlist,
  saveDemoWatchlist,
  type DemoTimeframe,
} from "../lib/demoData";

export const MAX_OPENED_TABS = 5;

export const TIMEFRAME_OPTIONS: Array<{ key: DemoTimeframe; label: string }> = [
  { key: "realtime", label: "Realtime" },
  { key: "day", label: "Day" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
];

type DetailSnapshot = {
  bars: MarketBar[];
  indicators: IndicatorBundle | null;
  timeframe: DemoTimeframe | null;
  loading: boolean;
  error: string | null;
  updatedAt: string | null;
};

type DisplayRenderable = {
  ticker: string;
  bars: MarketBar[];
  indicators: IndicatorBundle;
  updatedAt: string | null;
};

export type DemoTerminalModel = {
  watchlist: WatchlistItem[];
  watchlistBusy: boolean;
  watchlistError: string | null;
  tickerInput: string;
  openTickers: string[];
  activeTicker: string | null;
  tabMessage: string | null;
  timeframe: DemoTimeframe;
  activeDetail: DetailSnapshot | null;
  displayRenderable: DisplayRenderable | null;
  latestBar: MarketBar | undefined;
  hasDisplayData: boolean;
  showRefreshBadge: boolean;
  setTickerInput: React.Dispatch<React.SetStateAction<string>>;
  setTimeframe: React.Dispatch<React.SetStateAction<DemoTimeframe>>;
  refreshWatchlist: () => Promise<void>;
  reloadActiveTicker: () => void;
  openTicker: (ticker: string) => void;
  selectTicker: (ticker: string) => void;
  closeTicker: (ticker: string) => void;
  onAddTicker: () => void;
  onDeleteTicker: (ticker: string) => void;
};

type DemoTerminalDependencies = {
  now: () => Date;
  sleep: (milliseconds: number) => Promise<void>;
  storage: DemoStorage | null;
};

type DemoTerminalOptions = {
  dependencies?: Partial<DemoTerminalDependencies>;
};

export function useDemoTerminal(options?: DemoTerminalOptions): DemoTerminalModel {
  const resolvedDependencies = React.useMemo<DemoTerminalDependencies>(() => {
    const base = defaultDemoDataEnvironment();
    return {
      now: options?.dependencies?.now ?? base.now,
      sleep: options?.dependencies?.sleep ?? sleepWithTimeout,
      storage: options?.dependencies?.storage ?? base.storage,
    };
  }, [options?.dependencies?.now, options?.dependencies?.sleep, options?.dependencies?.storage]);

  const dataEnvironment = React.useMemo<DemoDataEnvironment>(
    () => ({
      now: resolvedDependencies.now,
      storage: resolvedDependencies.storage,
    }),
    [resolvedDependencies.now, resolvedDependencies.storage],
  );

  const [watchlist, setWatchlist] = React.useState<WatchlistItem[]>(() => loadDemoWatchlist(dataEnvironment));
  const [watchlistBusy, setWatchlistBusy] = React.useState(false);
  const [watchlistError, setWatchlistError] = React.useState<string | null>(null);
  const [tickerInput, setTickerInput] = React.useState("");

  const [openTickers, setOpenTickers] = React.useState<string[]>([]);
  const [activeTicker, setActiveTicker] = React.useState<string | null>(null);
  const [tabMessage, setTabMessage] = React.useState<string | null>(null);

  const [timeframe, setTimeframe] = React.useState<DemoTimeframe>("day");
  const [lastStableTicker, setLastStableTicker] = React.useState<string | null>(null);

  const [detailsByTicker, setDetailsByTicker] = React.useState<Record<string, DetailSnapshot>>({});
  const detailsRef = React.useRef<Record<string, DetailSnapshot>>({});
  const activeTickerRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    detailsRef.current = detailsByTicker;
  }, [detailsByTicker]);

  React.useEffect(() => {
    activeTickerRef.current = activeTicker;
  }, [activeTicker]);

  React.useEffect(() => {
    saveDemoWatchlist(watchlist, dataEnvironment);
  }, [watchlist, dataEnvironment]);

  const refreshWatchlist = React.useCallback(async () => {
    setWatchlistBusy(true);
    setWatchlistError(null);
    await resolvedDependencies.sleep(120);
    setWatchlist(loadDemoWatchlist(dataEnvironment));
    setWatchlistBusy(false);
  }, [dataEnvironment, resolvedDependencies]);

  const loadTickerDetail = React.useCallback(
    async (ticker: string, force = false) => {
      const existing = detailsRef.current[ticker];
      const isCurrentTimeframe = existing?.timeframe === timeframe;
      if (!force && isCurrentTimeframe && existing?.bars?.length) {
        return;
      }

      setDetailsByTicker((prev) => ({
        ...prev,
        [ticker]: {
          bars: prev[ticker]?.bars ?? [],
          indicators: prev[ticker]?.indicators ?? null,
          timeframe,
          loading: true,
          error: null,
          updatedAt: prev[ticker]?.updatedAt ?? null,
        },
      }));

      await resolvedDependencies.sleep(150);

      try {
        const bars = buildDemoBars(ticker, timeframe, resolvedDependencies.now);
        setDetailsByTicker((prev) => ({
          ...prev,
          [ticker]: {
            bars,
            indicators: buildIndicators(bars),
            timeframe,
            loading: false,
            error: null,
            updatedAt: resolvedDependencies.now().toISOString(),
          },
        }));
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : `Failed to load ${ticker}`;
        setDetailsByTicker((prev) => ({
          ...prev,
          [ticker]: {
            bars: prev[ticker]?.bars ?? [],
            indicators: prev[ticker]?.indicators ?? null,
            timeframe,
            loading: false,
            error: message,
            updatedAt: prev[ticker]?.updatedAt ?? null,
          },
        }));
      }
    },
    [resolvedDependencies, timeframe],
  );

  React.useEffect(() => {
    if (activeTickerRef.current) {
      void loadTickerDetail(activeTickerRef.current, true);
    }
  }, [timeframe, loadTickerDetail]);

  const openTicker = React.useCallback(
    (ticker: string) => {
      const normalized = ticker.toUpperCase();
      setTabMessage(null);

      let blocked = false;
      setOpenTickers((prev) => {
        if (prev.includes(normalized)) {
          return prev;
        }
        if (prev.length >= MAX_OPENED_TABS) {
          blocked = true;
          return prev;
        }
        return [...prev, normalized];
      });

      if (blocked) {
        setTabMessage(`Up to ${MAX_OPENED_TABS} detail tabs can be opened at once.`);
        return;
      }

      setActiveTicker(normalized);
      void loadTickerDetail(normalized);
    },
    [loadTickerDetail],
  );

  const closeTicker = React.useCallback((ticker: string) => {
    setOpenTickers((prev) => {
      const next = prev.filter((item) => item !== ticker);
      if (activeTickerRef.current === ticker) {
        setActiveTicker(next[next.length - 1] ?? null);
      }
      return next;
    });
  }, []);

  const selectTicker = React.useCallback(
    (ticker: string) => {
      setActiveTicker(ticker);
      void loadTickerDetail(ticker);
    },
    [loadTickerDetail],
  );

  const onAddTicker = React.useCallback(() => {
    const normalized = tickerInput.trim().toUpperCase();
    if (!normalized) return;
    if (!/^[A-Z.]{1,10}$/.test(normalized)) {
      setWatchlistError("Ticker format is invalid.");
      return;
    }

    if (watchlist.find((item) => item.ticker === normalized)) {
      setWatchlistError(`${normalized} already exists in demo watchlist.`);
      return;
    }

    setWatchlistError(null);
    setWatchlist((prev) => [...prev, { ticker: normalized }]);
    setTickerInput("");
    openTicker(normalized);
  }, [openTicker, tickerInput, watchlist]);

  const onDeleteTicker = React.useCallback((ticker: string) => {
    setWatchlist((prev) => prev.filter((item) => item.ticker !== ticker));
    setOpenTickers((prev) => prev.filter((item) => item !== ticker));
    if (activeTickerRef.current === ticker) {
      setActiveTicker(null);
    }
  }, []);

  const reloadActiveTicker = React.useCallback(() => {
    if (!activeTicker) {
      return;
    }
    void loadTickerDetail(activeTicker, true);
  }, [activeTicker, loadTickerDetail]);

  const activeDetail = activeTicker ? detailsByTicker[activeTicker] ?? null : null;
  const activeHasData = Boolean(activeTicker && activeDetail?.bars.length && activeDetail.indicators);
  const displayTicker = activeTicker ? (activeHasData ? activeTicker : lastStableTicker) : null;
  const displayDetail = displayTicker ? detailsByTicker[displayTicker] : null;

  const displayRenderable =
    displayTicker && displayDetail?.bars.length && displayDetail.indicators
      ? {
          ticker: displayTicker,
          bars: displayDetail.bars,
          indicators: displayDetail.indicators,
          updatedAt: displayDetail.updatedAt,
        }
      : null;

  const latestBar = displayRenderable?.bars.at(-1);
  const hasDisplayData = Boolean(displayRenderable);
  const showRefreshBadge = Boolean(activeTicker && activeDetail?.loading && displayRenderable);

  React.useEffect(() => {
    if (activeHasData && activeTicker) {
      setLastStableTicker(activeTicker);
    }
  }, [activeHasData, activeTicker]);

  return {
    watchlist,
    watchlistBusy,
    watchlistError,
    tickerInput,
    openTickers,
    activeTicker,
    tabMessage,
    timeframe,
    activeDetail,
    displayRenderable,
    latestBar,
    hasDisplayData,
    showRefreshBadge,
    setTickerInput,
    setTimeframe,
    refreshWatchlist,
    reloadActiveTicker,
    openTicker,
    selectTicker,
    closeTicker,
    onAddTicker,
    onDeleteTicker,
  };
}

export function timeframeLabel(timeframe: DemoTimeframe): string {
  return TIMEFRAME_OPTIONS.find((item) => item.key === timeframe)?.label ?? timeframe;
}

function sleepWithTimeout(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}
