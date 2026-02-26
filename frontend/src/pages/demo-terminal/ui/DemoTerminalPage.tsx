import React from "react";

import { StockChartPanel } from "@/entities/market";
import { type WatchlistItem } from "@/entities/watchlist";
import {
  MAX_OPENED_TABS,
  TIMEFRAME_OPTIONS,
  timeframeLabel,
  useDemoTerminal,
} from "@/features/demo-terminal";
import { TerminalEmptyGraphic } from "@/shared/ui";

export function DemoTerminalPage() {
  const {
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
  } = useDemoTerminal();

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
          <span className="pill">TF: {timeframeLabel(timeframe)}</span>
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
                    <WatchlistRow
                      key={item.ticker}
                      item={item}
                      onOpen={openTicker}
                      onDelete={onDeleteTicker}
                    />
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
                <button className="btn btnSecondary" type="button" onClick={reloadActiveTicker}>
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
                    onClick={() => selectTicker(ticker)}
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

            {activeTicker && activeDetail?.loading && !hasDisplayData ? (
              <div className="muted">Loading demo bars and indicators...</div>
            ) : null}
            {activeTicker && activeDetail?.error ? <div className="errorText">{activeDetail.error}</div> : null}

            {displayRenderable ? (
              <div className="detailRenderStack">
                {showRefreshBadge ? (
                  <div className="detailLoadingBadge">
                    {activeTicker !== displayRenderable.ticker
                      ? `Loading ${activeTicker}, showing ${displayRenderable.ticker}`
                      : `Refreshing ${activeTicker}`}
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

type WatchlistRowProps = {
  item: WatchlistItem;
  onOpen: (ticker: string) => void;
  onDelete: (ticker: string) => void;
};

function WatchlistRow({ item, onOpen, onDelete }: WatchlistRowProps) {
  return (
    <tr>
      <td>
        <button className="watchTicker" type="button" onClick={() => onOpen(item.ticker)}>
          {item.ticker}
        </button>
      </td>
      <td>
        <button className="btn btnSecondary" type="button" onClick={() => onDelete(item.ticker)}>
          Remove
        </button>
      </td>
    </tr>
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
