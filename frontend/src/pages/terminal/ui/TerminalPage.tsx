import React from "react";

import { buildIndicators, listMarketBars, type IndicatorBundle, type MarketBar } from "@/entities/market";
import { useSession } from "@/entities/session";
import { TerminalEmptyGraphic } from "@/shared/ui";
import {
  addWatchlist,
  deleteWatchlist,
  listWatchlist,
  type WatchlistItem
} from "@/entities/watchlist";
import { StockChartPanel } from "@/widgets/stock-chart";

type DetailSnapshot = {
  bars: MarketBar[];
  indicators: IndicatorBundle | null;
  timeframe: TimeframeKey | null;
  loading: boolean;
  error: string | null;
  updatedAt: string | null;
};

type TimeframeKey = "realtime" | "day" | "week" | "month";

const MAX_OPENED_TABS = 5;

const TIMEFRAME_OPTIONS: Array<{ key: TimeframeKey; label: string }> = [
  { key: "realtime", label: "Realtime" },
  { key: "day", label: "Day" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" }
];

export function TerminalPage() {
  const { token, user } = useSession();

  const [watchlist, setWatchlist] = React.useState<WatchlistItem[]>([]);
  const [watchlistBusy, setWatchlistBusy] = React.useState(false);
  const [watchlistError, setWatchlistError] = React.useState<string | null>(null);
  const [tickerInput, setTickerInput] = React.useState("");

  const [openTickers, setOpenTickers] = React.useState<string[]>([]);
  const [activeTicker, setActiveTicker] = React.useState<string | null>(null);
  const [tabMessage, setTabMessage] = React.useState<string | null>(null);

  const [timeframe, setTimeframe] = React.useState<TimeframeKey>("day");
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

  const refreshWatchlist = React.useCallback(async () => {
    if (!token) return;
    setWatchlistBusy(true);
    setWatchlistError(null);
    try {
      const items = await listWatchlist(token);
      setWatchlist(items);
    } catch (error: any) {
      setWatchlistError(error?.message ?? "Failed to load watchlist.");
    } finally {
      setWatchlistBusy(false);
    }
  }, [token]);

  React.useEffect(() => {
    void refreshWatchlist();
  }, [refreshWatchlist]);

  const loadTickerDetail = React.useCallback(
    async (ticker: string, force = false) => {
      if (!token) return;

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
          updatedAt: prev[ticker]?.updatedAt ?? null
        }
      }));

      try {
        const query = marketQueryForTimeframe(timeframe);
        const bars = await listMarketBars({
          token,
          ticker,
          timespan: query.timespan,
          multiplier: query.multiplier,
          from: dateOffset(query.fromDays),
          to: dateOffset(0),
          limit: query.limit
        });

        const sortedBars = [...bars].sort((left, right) =>
          new Date(left.start_at).getTime() - new Date(right.start_at).getTime()
        );

        setDetailsByTicker((prev) => ({
          ...prev,
          [ticker]: {
            bars: sortedBars,
            indicators: buildIndicators(sortedBars),
            timeframe,
            loading: false,
            error: null,
            updatedAt: new Date().toISOString()
          }
        }));
      } catch (error: any) {
        setDetailsByTicker((prev) => ({
          ...prev,
          [ticker]: {
            bars: prev[ticker]?.bars ?? [],
            indicators: prev[ticker]?.indicators ?? null,
            timeframe,
            loading: false,
            error: error?.message ?? `Failed to load ${ticker}`,
            updatedAt: prev[ticker]?.updatedAt ?? null
          }
        }));
      }
    },
    [timeframe, token]
  );

  React.useEffect(() => {
    if (activeTickerRef.current) {
      void loadTickerDetail(activeTickerRef.current, true);
    }
  }, [timeframe, loadTickerDetail]);

  function openTicker(ticker: string) {
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
  }

  function closeTicker(ticker: string) {
    setOpenTickers((prev) => {
      const next = prev.filter((item) => item !== ticker);
      if (activeTickerRef.current === ticker) {
        setActiveTicker(next[next.length - 1] ?? null);
      }
      return next;
    });
  }

  async function onAddTicker() {
    if (!token) return;
    const normalized = tickerInput.trim().toUpperCase();
    if (!normalized) return;

    setWatchlistError(null);
    try {
      await addWatchlist(token, normalized);
      setTickerInput("");
      await refreshWatchlist();
      openTicker(normalized);
    } catch (error: any) {
      setWatchlistError(error?.message ?? "Failed to add ticker.");
    }
  }

  async function onDeleteTicker(ticker: string) {
    if (!token) return;

    setWatchlistError(null);
    try {
      await deleteWatchlist(token, ticker);
      setOpenTickers((prev) => prev.filter((item) => item !== ticker));
      if (activeTickerRef.current === ticker) {
        setActiveTicker(null);
      }
      await refreshWatchlist();
    } catch (error: any) {
      setWatchlistError(error?.message ?? "Failed to delete ticker.");
    }
  }

  const activeDetail = activeTicker ? detailsByTicker[activeTicker] : null;
  const activeHasData = Boolean(activeTicker && activeDetail?.bars.length && activeDetail.indicators);
  const displayTicker = activeTicker ? (activeHasData ? activeTicker : lastStableTicker) : null;
  const displayDetail = displayTicker ? detailsByTicker[displayTicker] : null;
  const displayRenderable = displayTicker && displayDetail?.bars.length && displayDetail.indicators
    ? {
      ticker: displayTicker,
      bars: displayDetail.bars,
      indicators: displayDetail.indicators,
      updatedAt: displayDetail.updatedAt
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

  return (
    <main className="terminalPage">
      <section className="terminalHead panel">
        <div className="panelHeader">
          <div className="panelTitle">TRADING TERMINAL</div>
          <div className="panelMeta">{user?.email}</div>
        </div>
        <div className="panelBody row terminalHeadBody">
          <span className="pill">Session: {token ? "Authenticated" : "Guest"}</span>
          <span className="pill">Watchlist: {watchlist.length}</span>
          <span className="pill">Opened tabs: {openTickers.length}/{MAX_OPENED_TABS}</span>
          <span className="pill">TF: {timeframeLabel(timeframe)}</span>
        </div>
      </section>

      <div className="terminalGrid">
        <aside className="panel watchlistPanel">
          <div className="panelHeader">
            <div className="panelTitle">WATCHLIST</div>
            <div className="panelMeta">{watchlistBusy ? "Syncing..." : "Live"}</div>
          </div>
          <div className="panelBody">
            <div className="row">
              <input
                className="input"
                placeholder="Ticker (AAPL, NVDA...)"
                value={tickerInput}
                onChange={(event) => setTickerInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    void onAddTicker();
                  }
                }}
              />
              <button className="btn" type="button" onClick={() => void onAddTicker()}>
                Add
              </button>
              <button className="btn btnSecondary" type="button" onClick={() => void refreshWatchlist()}>
                Refresh
              </button>
            </div>

            {watchlistError ? <div className="errorText">{watchlistError}</div> : null}
            {tabMessage ? <div className="muted">{tabMessage}</div> : null}

            <table className="table watchlistTable">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {watchlist.length === 0 ? (
                  <tr>
                    <td colSpan={2} className="muted">
                      No symbols yet.
                    </td>
                  </tr>
                ) : (
                  watchlist.map((item) => (
                    <tr key={item.ticker}>
                      <td>
                        <button className="watchTicker" type="button" onClick={() => openTicker(item.ticker)}>
                          {item.ticker}
                        </button>
                      </td>
                      <td>
                        <button
                          className="btn btnSecondary"
                          type="button"
                          onClick={() => void onDeleteTicker(item.ticker)}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </aside>

        <section className="panel detailPanel">
          <div className="panelHeader">
            <div className="panelTitle">DETAIL VIEW</div>
            {activeTicker ? (
              <div className="panelMeta row">
                <span>{activeTicker}</span>
                <button
                  className="btn btnSecondary"
                  type="button"
                  onClick={() => void loadTickerDetail(activeTicker, true)}
                >
                  Reload
                </button>
              </div>
            ) : (
              <div className="panelMeta">Select a ticker</div>
            )}
          </div>
          <div className="panelBody detailBody">
            <div className="timeframeRow">
              {TIMEFRAME_OPTIONS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`timeframeBtn ${timeframe === item.key ? "timeframeBtnActive" : ""}`}
                  onClick={() => setTimeframe(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {openTickers.length ? (
              <div className="tabRow">
                {openTickers.map((ticker) => (
                  <button
                    key={ticker}
                    type="button"
                    className={`tabChip ${ticker === activeTicker ? "tabChipActive" : ""}`}
                    onClick={() => {
                      setActiveTicker(ticker);
                      void loadTickerDetail(ticker);
                    }}
                  >
                    {ticker}
                    <span
                      role="button"
                      tabIndex={0}
                      className="tabClose"
                      onClick={(event) => {
                        event.stopPropagation();
                        closeTicker(ticker);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.stopPropagation();
                          closeTicker(ticker);
                        }
                      }}
                    >
                      x
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="emptyState">
                <TerminalEmptyGraphic />
                <p className="muted">Open a symbol from watchlist to inspect details.</p>
              </div>
            )}

            {activeTicker && activeDetail?.loading && !hasDisplayData ? <div className="muted">Loading bars and indicators...</div> : null}
            {activeTicker && activeDetail?.error ? <div className="errorText">{activeDetail.error}</div> : null}

            {displayRenderable ? (
              <div className="detailRenderStack">
                {showRefreshBadge ? (
                  <div className="detailLoadingBadge">
                    {activeTicker !== displayRenderable.ticker ? `Loading ${activeTicker}, showing ${displayRenderable.ticker}` : `Refreshing ${activeTicker}`}
                  </div>
                ) : null}
                <div className="metricRow">
                  <MetricCard label="TF" value={timeframeLabel(timeframe)} />
                  <MetricCard label="Last" value={toPrice(latestBar?.close)} />
                  <MetricCard label="High" value={toPrice(latestBar?.high)} />
                  <MetricCard label="Low" value={toPrice(latestBar?.low)} />
                  <MetricCard label="Volume" value={toVolume(latestBar?.volume)} />
                  <MetricCard label="Updated" value={formatTime(displayRenderable.updatedAt)} />
                </div>
                <StockChartPanel
                  ticker={displayRenderable.ticker}
                  bars={displayRenderable.bars}
                  indicators={displayRenderable.indicators}
                />
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </main>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="metricCard">
      <div className="metricLabel">{label}</div>
      <div className="metricValue">{value}</div>
    </article>
  );
}

function dateOffset(days: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function toPrice(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "-";
  return `$${value.toFixed(2)}`;
}

function toVolume(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "-";
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return value.toFixed(0);
}

function formatTime(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleTimeString();
}

function timeframeLabel(timeframe: TimeframeKey): string {
  return TIMEFRAME_OPTIONS.find((item) => item.key === timeframe)?.label ?? timeframe;
}

function marketQueryForTimeframe(timeframe: TimeframeKey): {
  timespan: string;
  multiplier: number;
  fromDays: number;
  limit: number;
} {
  switch (timeframe) {
    case "realtime":
      return { timespan: "minute", multiplier: 5, fromDays: -14, limit: 4000 };
    case "week":
      return { timespan: "week", multiplier: 1, fromDays: -3650, limit: 600 };
    case "month":
      return { timespan: "month", multiplier: 1, fromDays: -7300, limit: 300 };
    case "day":
    default:
      return { timespan: "day", multiplier: 1, fromDays: -320, limit: 800 };
  }
}
