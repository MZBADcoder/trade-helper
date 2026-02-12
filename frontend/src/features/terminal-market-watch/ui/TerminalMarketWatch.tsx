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
import { type OptionTypeFilter } from "../model/types";

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
  } = useTerminalMarketWatch();

  const streamLabel = streamStatusLabel(streamStatus);
  const streamClass = streamStatusClass(streamStatus);

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

        <aside className="panel optionsPanel">
          <div className="panelHeader">
            <div className="panelTitle">OPTIONS WORKSPACE</div>
            <div className="panelMeta">{activeTicker ?? "Select ticker"}</div>
          </div>

          <div className="panelBody optionsBody">
            {!activeTicker ? (
              <div className="muted">先在 watchlist 选择股票，再查看对应期权链。</div>
            ) : (
              <>
                <div className="optionsControlRow">
                  <label className="fieldLabel" htmlFor="expiration-select">
                    Expiration
                  </label>
                  <select
                    id="expiration-select"
                    className="input selectInput"
                    value={selectedExpiration ?? ""}
                    onChange={(event) => setSelectedExpiration(event.target.value || null)}
                    disabled={expirationsBusy || !expirations.length}
                  >
                    {!expirations.length ? <option value="">No data</option> : null}
                    {expirations.map((item) => (
                      <option key={item.date} value={item.date}>
                        {item.date} ({item.days_to_expiration}D)
                      </option>
                    ))}
                  </select>
                </div>

                <div className="optionsControlRow">
                  <label className="fieldLabel" htmlFor="option-type-select">
                    Option Type
                  </label>
                  <select
                    id="option-type-select"
                    className="input selectInput"
                    value={optionTypeFilter}
                    onChange={(event) => setOptionTypeFilter(event.target.value as OptionTypeFilter)}
                  >
                    <option value="all">All</option>
                    <option value="call">Call</option>
                    <option value="put">Put</option>
                  </select>
                </div>

                <div className="row">
                  <button
                    className="btn btnSecondary"
                    type="button"
                    onClick={() => activeTicker && void loadExpirations(activeTicker)}
                  >
                    Reload Expirations
                  </button>
                  <button
                    className="btn btnSecondary"
                    type="button"
                    onClick={() => activeTicker && selectedExpiration && void loadOptionChainData(activeTicker, selectedExpiration)}
                    disabled={!selectedExpiration}
                  >
                    Reload Chain
                  </button>
                </div>

                {expirationsBusy ? <div className="muted">Loading expirations...</div> : null}
                {chainBusy ? <div className="muted">Loading option chain...</div> : null}
                {expirationsError ? <div className="errorText">{expirationsError}</div> : null}
                {chainError ? <div className="errorText">{chainError}</div> : null}

                <div className="tableWrap optionsTableWrap">
                  <table className="table optionsChainTable">
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Strike</th>
                        <th>Bid</th>
                        <th>Ask</th>
                        <th>Last</th>
                        <th>IV</th>
                        <th>Vol</th>
                        <th>OI</th>
                      </tr>
                    </thead>
                    <tbody>
                      {!optionChain.length ? (
                        <tr>
                          <td colSpan={8} className="muted">
                            选择到期日后加载期权链（最多渲染 200 行）。
                          </td>
                        </tr>
                      ) : (
                        optionChain.map((item) => {
                          const selected = item.option_ticker === selectedContractTicker;
                          return (
                            <tr key={item.option_ticker} className={selected ? "optionsRowActive" : ""}>
                              <td>
                                <button
                                  className="chainTickerBtn"
                                  type="button"
                                  onClick={() => setSelectedContractTicker(item.option_ticker)}
                                >
                                  {item.option_type.toUpperCase()}
                                </button>
                              </td>
                              <td>{toPrice(item.strike)}</td>
                              <td>{renderMaybeNumber(item.bid, toPrice)}</td>
                              <td>{renderMaybeNumber(item.ask, toPrice)}</td>
                              <td>{renderMaybeNumber(item.last, toPrice)}</td>
                              <td>{renderMaybeNumber(item.iv, (value) => `${(value * 100).toFixed(1)}%`)}</td>
                              <td>{renderMaybeNumber(item.volume, (value) => toVolume(value))}</td>
                              <td>{renderMaybeNumber(item.open_interest, (value) => toVolume(value))}</td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>

                {selectedContractTicker ? (
                  <div className="optionContractCard">
                    <div className="optionContractHeader">
                      <span className="panelTitle">CONTRACT DETAIL</span>
                      <span className="panelMeta">{selectedContractTicker}</span>
                    </div>

                    {contractBusy ? <div className="muted">Loading contract detail...</div> : null}
                    {contractError ? <div className="errorText">{contractError}</div> : null}

                    {contractDetail ? (
                      <div className="optionMetricGrid">
                        <MetricCard label="Bid" value={toPrice(contractDetail.quote.bid)} />
                        <MetricCard label="Ask" value={toPrice(contractDetail.quote.ask)} />
                        <MetricCard label="Last" value={toPrice(contractDetail.quote.last)} />
                        <MetricCard label="Strike" value={toPrice(contractDetail.strike)} />
                        <MetricCard label="Volume" value={toVolume(contractDetail.session.volume)} />
                        <MetricCard label="OI" value={toVolume(contractDetail.session.open_interest)} />
                        <MetricCard label="Delta" value={toSigned(contractDetail.greeks?.delta)} />
                        <MetricCard label="Gamma" value={toSigned(contractDetail.greeks?.gamma)} />
                        <MetricCard label="Theta" value={toSigned(contractDetail.greeks?.theta)} />
                        <MetricCard label="Vega" value={toSigned(contractDetail.greeks?.vega)} />
                        <MetricCard
                          label="IV"
                          value={
                            contractDetail.greeks?.iv === null || contractDetail.greeks?.iv === undefined
                              ? "-"
                              : `${(contractDetail.greeks.iv * 100).toFixed(1)}%`
                          }
                        />
                        <MetricCard label="Source" value={contractDetail.source} />
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </>
            )}
          </div>
        </aside>
      </div>

      <section className="panel statusBarPanel">
        <div className="panelBody statusBarBody">
          <span className={`statusBadge ${streamClass}`}>{streamLabel}</span>
          <span className="statusField">Source: {streamSource}</span>
          <span className="statusField">Latency: {dataLatency}</span>
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

function renderMaybeNumber(
  value: number | null | undefined,
  formatter: (value: number) => string
): React.ReactNode {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return (
      <span className="fieldFallback" title="上游字段不可用">
        -
      </span>
    );
  }
  return formatter(value);
}
