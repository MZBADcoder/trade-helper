import React from "react";

import { StockChartPanel } from "@/entities/market";
import { TerminalEmptyGraphic } from "@/shared/ui";

import {
  formatDateTime,
  formatTime,
  shrinkText,
  snapshotToneClass,
  streamStatusClass,
  streamStatusLabel,
  toPrice,
  toSigned,
  toSignedPercent,
  toVolume
} from "../lib/presentation";
import { TIMEFRAME_OPTIONS, useTerminalMarketWatch } from "../model/useTerminalMarketWatch";

export function TerminalMarketWatch() {
  const {
    userEmail,
    isAuthenticated,
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
    realtimeEnabled,
    delayMinutes,
    lastSyncAt,
    lastError
  } = useTerminalMarketWatch();

  const streamLabel = streamStatusLabel(streamStatus);
  const streamClass = streamStatusClass(streamStatus);
  const delayedHintLabel = `Delayed by ${delayMinutes} minutes`;

  return (
    <main className="terminalPage terminalPageV2">
      <section className="terminalHead panel">
        <div className="panelHeader">
          <div className="panelTitle">MARKET WATCH TERMINAL</div>
          <div className="panelMeta">{userEmail}</div>
        </div>
        <div className="panelBody row terminalHeadBody">
          <span className="pill">Session: {isAuthenticated ? "Authenticated" : "Guest"}</span>
          <span className="pill">Watchlist: {watchlist.length}</span>
          <span className="pill">Selected: {activeTicker ?? "-"}</span>
          <span className={`pill statusPill ${streamClass}`}>Stream: {streamLabel}</span>
          {!realtimeEnabled ? <span className="pill statusDegraded">{delayedHintLabel}</span> : null}
        </div>
      </section>

      <div className="terminalGrid terminalV2Grid">
        <aside className="panel watchlistPanel watchlistPanelV2">
          <div className="panelHeader">
            <div className="panelTitle">WATCHLIST</div>
            <div className="panelMeta">{watchlistBusy ? "Syncing..." : "Live Snapshot"}</div>
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

            <div className="tableWrap">
              <table className="table watchlistTable watchlistTableV2">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Last</th>
                    <th>Change</th>
                    <th>%</th>
                    <th>Updated</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {watchlist.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="muted">
                        先添加 ticker 以开始观察行情。
                      </td>
                    </tr>
                  ) : (
                    watchlist.map((item) => {
                      const symbol = item.ticker;
                      const snapshot = snapshotMap[symbol];
                      const rowClass = symbol === activeTicker ? "watchRowActive" : "";
                      const changeClass = snapshotToneClass(snapshot?.change ?? 0);

                      return (
                        <tr key={symbol} className={rowClass}>
                          <td>
                            <button className="watchTicker" type="button" onClick={() => onSelectTicker(symbol)}>
                              {symbol}
                            </button>
                          </td>
                          <td>{toPrice(snapshot?.last)}</td>
                          <td className={changeClass}>{toSigned(snapshot?.change)}</td>
                          <td className={changeClass}>{toSignedPercent(snapshot?.change_pct)}</td>
                          <td>{formatTime(snapshot?.updated_at ?? null)}</td>
                          <td>
                            <button className="btn btnSecondary" type="button" onClick={() => void onDeleteTicker(symbol)}>
                              Remove
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </aside>

        <section className="panel detailPanel detailPanelV2">
          <div className="panelHeader">
            <div className="panelTitle">DETAIL WORKSPACE</div>
            {activeTicker ? (
              <div className="panelMeta row">
                <span>{activeTicker}</span>
                <button className="btn btnSecondary" type="button" onClick={() => void loadTickerDetail(activeTicker, true)}>
                  Reload Bars
                </button>
                <button className="btn btnSecondary" type="button" onClick={() => void refreshSnapshots([activeTicker])}>
                  Reload Snapshot
                </button>
              </div>
            ) : (
              <div className="panelMeta">Select a ticker</div>
            )}
          </div>

          <div className="panelBody detailBody detailBodyV2">
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

            {activeTicker ? (
              <>
                <div className="detailStatusRow">
                  <span className={`statusDot ${streamClass}`} />
                  <span>{streamLabel}</span>
                  <span className={`sourceTag ${streamSource !== "WS" ? "sourceTagDelayed" : ""}`}>
                    Source: {activeSnapshot?.source ?? activeDetail?.source ?? streamSource}
                  </span>
                  <span className="sourceTag">Bars: {activeDetail?.barsDataSource ?? "-"}</span>
                  <span className="pill">Market: {activeSnapshot?.market_status ?? "-"}</span>
                </div>

                <div className="metricRow metricRowV2">
                  <MetricCard label="Last" value={toPrice(activeSnapshot?.last ?? latestBar?.close)} />
                  <MetricCard
                    label="Change"
                    value={toSigned(activeSnapshot?.change)}
                    tone={snapshotToneClass(activeSnapshot?.change ?? 0)}
                  />
                  <MetricCard
                    label="%Change"
                    value={toSignedPercent(activeSnapshot?.change_pct)}
                    tone={snapshotToneClass(activeSnapshot?.change ?? 0)}
                  />
                  <MetricCard label="High" value={toPrice(activeSnapshot?.high ?? latestBar?.high)} />
                  <MetricCard label="Low" value={toPrice(activeSnapshot?.low ?? latestBar?.low)} />
                  <MetricCard label="Volume" value={toVolume(activeSnapshot?.volume ?? latestBar?.volume)} />
                  <MetricCard label="Updated" value={formatTime(activeSnapshot?.updated_at ?? activeDetail?.updatedAt ?? null)} />
                  <MetricCard label="Latency" value={dataLatency} />
                </div>

                {activeDetail?.loading ? <div className="muted">Loading bars and indicators...</div> : null}
                {activeDetail?.error ? <div className="errorText">{activeDetail.error}</div> : null}

                {activeDetail?.bars.length && activeDetail.indicators ? (
                  <StockChartPanel ticker={activeTicker} bars={activeDetail.bars} indicators={activeDetail.indicators} />
                ) : (
                  <div className="emptyState">
                    <TerminalEmptyGraphic />
                    <p className="muted">No bars available for current symbol and timeframe.</p>
                  </div>
                )}
              </>
            ) : (
              <div className="emptyState">
                <TerminalEmptyGraphic />
                <p className="muted">从左侧选择 ticker 后展示股票详情与图表。</p>
              </div>
            )}
          </div>
        </section>

      </div>

      <section className="panel statusBarPanel">
        <div className="panelBody statusBarBody">
          <span className={`statusBadge ${streamClass}`}>{streamLabel}</span>
          <span className="statusField">Source: {streamSource}</span>
          <span className="statusField">Latency: {dataLatency}</span>
          {!realtimeEnabled ? <span className="statusField statusDegraded">{delayedHintLabel}</span> : null}
          <span className="statusField">Last Sync: {formatDateTime(lastSyncAt)}</span>
          <span className={`statusField ${lastError ? "statusFieldWarn" : ""}`}>
            Last Error: {lastError ? shrinkText(lastError, 96) : "-"}
          </span>
        </div>
      </section>
    </main>
  );
}

function MetricCard({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <article className={`metricCard ${tone ?? ""}`.trim()}>
      <div className="metricLabel">{label}</div>
      <div className="metricValue">{value}</div>
    </article>
  );
}
