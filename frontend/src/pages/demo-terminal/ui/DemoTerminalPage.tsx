import React from "react";

import { buildIndicators, type IndicatorBundle, type MarketBar } from "@/entities/market";
import { TerminalEmptyGraphic } from "@/shared/ui";
import { type WatchlistItem } from "@/entities/watchlist";
import { StockChartPanel } from "@/widgets/stock-chart";

import { buildDemoBars, loadDemoWatchlist, saveDemoWatchlist } from "../lib/demoData";

type DetailSnapshot = {
  bars: MarketBar[];
  indicators: IndicatorBundle | null;
  loading: boolean;
  error: string | null;
  updatedAt: string | null;
};

const MAX_OPENED_TABS = 5;

export function DemoTerminalPage() {
  const [watchlist, setWatchlist] = React.useState<WatchlistItem[]>(() => loadDemoWatchlist());
  const [watchlistBusy, setWatchlistBusy] = React.useState(false);
  const [watchlistError, setWatchlistError] = React.useState<string | null>(null);
  const [tickerInput, setTickerInput] = React.useState("");

  const [openTickers, setOpenTickers] = React.useState<string[]>([]);
  const [activeTicker, setActiveTicker] = React.useState<string | null>(null);
  const [tabMessage, setTabMessage] = React.useState<string | null>(null);

  const [detailsByTicker, setDetailsByTicker] = React.useState<Record<string, DetailSnapshot>>({});

  React.useEffect(() => {
    saveDemoWatchlist(watchlist);
  }, [watchlist]);

  const refreshWatchlist = React.useCallback(async () => {
    setWatchlistBusy(true);
    setWatchlistError(null);
    await delay(120);
    setWatchlist(loadDemoWatchlist());
    setWatchlistBusy(false);
  }, []);

  const loadTickerDetail = React.useCallback(
    async (ticker: string, force = false) => {
      const existing = detailsByTicker[ticker];
      if (!force && existing?.bars?.length) {
        return;
      }

      setDetailsByTicker((prev) => ({
        ...prev,
        [ticker]: {
          bars: prev[ticker]?.bars ?? [],
          indicators: prev[ticker]?.indicators ?? null,
          loading: true,
          error: null,
          updatedAt: prev[ticker]?.updatedAt ?? null
        }
      }));

      await delay(160);

      try {
        const bars = buildDemoBars(ticker, 300);
        setDetailsByTicker((prev) => ({
          ...prev,
          [ticker]: {
            bars,
            indicators: buildIndicators(bars),
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
            loading: false,
            error: error?.message ?? `Failed to load ${ticker}`,
            updatedAt: prev[ticker]?.updatedAt ?? null
          }
        }));
      }
    },
    [detailsByTicker]
  );

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
      if (activeTicker === ticker) {
        setActiveTicker(next[next.length - 1] ?? null);
      }
      return next;
    });
  }

  function onAddTicker() {
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
    const next = [...watchlist, { ticker: normalized }];
    setWatchlist(next);
    setTickerInput("");
    openTicker(normalized);
  }

  function onDeleteTicker(ticker: string) {
    const next = watchlist.filter((item) => item.ticker !== ticker);
    setWatchlist(next);
    setOpenTickers((prev) => prev.filter((item) => item !== ticker));
    if (activeTicker === ticker) {
      setActiveTicker(null);
    }
  }

  const activeDetail = activeTicker ? detailsByTicker[activeTicker] : null;
  const latestBar = activeDetail?.bars.at(-1);

  return (
    <main className="terminalPage">
      <section className="terminalHead panel">
        <div className="panelHeader">
          <div className="panelTitle">DEMO TERMINAL</div>
          <div className="panelMeta">Independent demo route (local data)</div>
        </div>
        <div className="panelBody row terminalHeadBody">
          <span className="pill">Session: Demo</span>
          <span className="pill">Data: Local synthetic market bars</span>
          <span className="pill">Opened tabs: {openTickers.length}/{MAX_OPENED_TABS}</span>
        </div>
      </section>

      <div className="terminalGrid">
        <aside className="panel watchlistPanel">
          <div className="panelHeader">
            <div className="panelTitle">DEMO WATCHLIST</div>
            <div className="panelMeta">{watchlistBusy ? "Syncing..." : "Local"}</div>
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
                    onAddTicker();
                  }
                }}
              />
              <button className="btn" type="button" onClick={onAddTicker}>
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
                        <button className="btn btnSecondary" type="button" onClick={() => onDeleteTicker(item.ticker)}>
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
                <p className="muted">Open a symbol from demo watchlist to inspect details.</p>
              </div>
            )}

            {activeTicker && activeDetail?.loading ? <div className="muted">Loading demo bars and indicators...</div> : null}
            {activeTicker && activeDetail?.error ? <div className="errorText">{activeDetail.error}</div> : null}

            {activeTicker && activeDetail?.bars.length && activeDetail.indicators ? (
              <>
                <div className="metricRow">
                  <MetricCard label="Last" value={toPrice(latestBar?.close)} />
                  <MetricCard label="High" value={toPrice(latestBar?.high)} />
                  <MetricCard label="Low" value={toPrice(latestBar?.low)} />
                  <MetricCard label="Volume" value={toVolume(latestBar?.volume)} />
                  <MetricCard label="Updated" value={formatTime(activeDetail.updatedAt)} />
                </div>
                <StockChartPanel
                  ticker={activeTicker}
                  bars={activeDetail.bars}
                  indicators={activeDetail.indicators}
                />
              </>
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

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
