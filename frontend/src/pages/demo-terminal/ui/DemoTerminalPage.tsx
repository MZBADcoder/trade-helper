import React from "react";

import { StockChartPanel } from "@/entities/market";
import {
  DEMO_REPLAY_WINDOW_LABEL,
  DemoMetricCard,
  formatReplayTime,
  toPrice,
  toSigned,
  toSignedPercent,
  toVolume,
  useDemoTerminal
} from "@/features/demo-terminal";
import { TerminalEmptyGraphic } from "@/shared/ui";

export function DemoTerminalPage() {
  const {
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
    activeTicker,
    reload
  } = useDemoTerminal();

  return (
    <main className="terminalPage">
      <section className="terminalHead panel">
        <div className="panelHeader">
          <div className="panelTitle">DEMO TERMINAL</div>
          <div className="panelMeta">Backend mock replay (no Massive dependency)</div>
        </div>
        <div className="panelBody row terminalHeadBody">
          <span className="pill">Session: Demo (No Login)</span>
          <span className="pill">Ticker: AMD</span>
          <span className="pill">Window: {DEMO_REPLAY_WINDOW_LABEL}</span>
          <span className="pill">Stream: {streamStatus}</span>
          <span className="pill">Bars Source: {dataSource ?? "-"}</span>
        </div>
      </section>

      <div className="terminalGrid">
        <aside className="panel watchlistPanel">
          <div className="panelHeader">
            <div className="panelTitle">DEMO WATCHLIST</div>
            <div className="panelMeta">{watchlistBusy ? "Syncing..." : "Fixed"}</div>
          </div>
          <div className="panelBody">
            <div className="row">
              <button className="btn btnSecondary" type="button" onClick={() => void reload()}>
                Reload Snapshot
              </button>
            </div>

            {watchlistError ? <div className="errorText">{watchlistError}</div> : null}
            {error ? <div className="errorText">{error}</div> : null}

            <table className="table watchlistTable">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Last</th>
                  <th>Change</th>
                  <th>%</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {watchlist.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="muted">
                      No symbols available.
                    </td>
                  </tr>
                ) : (
                  watchlist.map((item) => (
                    <tr key={item.ticker}>
                      <td>{item.ticker}</td>
                      <td>{toPrice(snapshot?.last)}</td>
                      <td>{toSigned(snapshot?.change)}</td>
                      <td>{toSignedPercent(snapshot?.change_pct)}</td>
                      <td>{formatReplayTime(snapshot?.updated_at ?? null)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </aside>

        <section className="panel detailPanel">
          <div className="panelHeader">
            <div className="panelTitle">REPLAY DETAIL</div>
            <div className="panelMeta row">
              <span>{activeTicker}</span>
              <span>{streamMessage ?? "Looping 30-minute market replay window"}</span>
            </div>
          </div>
          <div className="panelBody detailBody">
            {loading ? <div className="muted">Loading backend replay data...</div> : null}

            {snapshot ? (
              <div className="metricRow">
                <DemoMetricCard label="Last" value={toPrice(snapshot.last)} />
                <DemoMetricCard label="Change" value={toSigned(snapshot.change)} />
                <DemoMetricCard label="%Change" value={toSignedPercent(snapshot.change_pct)} />
                <DemoMetricCard label="High" value={toPrice(snapshot.high)} />
                <DemoMetricCard label="Low" value={toPrice(snapshot.low)} />
                <DemoMetricCard label="Volume" value={toVolume(snapshot.volume)} />
                <DemoMetricCard label="Updated" value={formatReplayTime(snapshot.updated_at)} />
                <DemoMetricCard label="Status" value={snapshot.market_status} />
              </div>
            ) : null}

            {bars.length && indicators ? (
              <StockChartPanel ticker={activeTicker} timeframe="1m" bars={bars} indicators={indicators} />
            ) : (
              <div className="emptyState">
                <TerminalEmptyGraphic />
                <p className="muted">Waiting for replay bars...</p>
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
