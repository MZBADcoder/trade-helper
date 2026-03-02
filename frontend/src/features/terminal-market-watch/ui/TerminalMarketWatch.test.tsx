import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { type TerminalMarketWatchViewModel } from "../model/types";

const { useTerminalMarketWatchMock } = vi.hoisted(() => ({
  useTerminalMarketWatchMock: vi.fn()
}));

vi.mock("../model/useTerminalMarketWatch", () => ({
  useTerminalMarketWatch: useTerminalMarketWatchMock
}));

vi.mock("../model/marketWatchUtils", () => ({
  TIMEFRAME_OPTIONS: [
    { key: "1m", label: "1m" },
    { key: "5m", label: "5m" },
    { key: "15m", label: "15m" },
    { key: "60m", label: "60m" },
    { key: "day", label: "Day" },
    { key: "week", label: "Week" },
    { key: "month", label: "Month" }
  ],
  SESSION_OPTIONS: [
    { key: "regular", label: "盘中" },
    { key: "pre", label: "盘前" },
    { key: "night", label: "夜盘" }
  ]
}));

import { TerminalMarketWatch } from "./TerminalMarketWatch";

function createViewModel(
  overrides: Partial<TerminalMarketWatchViewModel> = {}
): TerminalMarketWatchViewModel {
  return {
    userEmail: "trader@test.dev",
    isAuthenticated: true,
    watchlist: [{ ticker: "AAPL" }],
    watchlistBusy: false,
    watchlistError: null,
    tickerInput: "",
    setTickerInput: vi.fn(),
    refreshWatchlist: vi.fn(async () => undefined),
    onAddTicker: vi.fn(async () => undefined),
    onDeleteTicker: vi.fn(async () => undefined),
    onSelectTicker: vi.fn(),
    activeTicker: "AAPL",
    snapshotMap: {},
    timeframe: "5m",
    setTimeframe: vi.fn(),
    session: "regular",
    setSession: vi.fn(),
    activeDetail: {
      bars: [],
      indicators: null,
      timeframe: "5m",
      loading: false,
      loadingMoreBefore: false,
      hasMoreBefore: false,
      earliestLoadedAt: null,
      lookbackStartDate: null,
      nextFetchEndDate: null,
      error: null,
      updatedAt: null,
      source: "REST",
      barsDataSource: "DB_AGG_MIXED"
    },
    activeSnapshot: null,
    latestBar: undefined,
    loadTickerDetail: vi.fn(async () => undefined),
    loadMoreTickerHistory: vi.fn(async () => undefined),
    refreshSnapshots: vi.fn(async () => undefined),
    streamStatus: "connected",
    streamSource: "REST",
    dataLatency: "delayed",
    delayMinutes: 15,
    lastSyncAt: null,
    lastError: null,
    ...overrides
  };
}

describe("TerminalMarketWatch", () => {
  it("shows bars data source from X-Data-Source", () => {
    useTerminalMarketWatchMock.mockReturnValue(createViewModel());

    render(<TerminalMarketWatch />);

    expect(screen.getByText("Bars: DB_AGG_MIXED")).toBeTruthy();
  });

  it("shows '-' when bars data source is missing", () => {
    useTerminalMarketWatchMock.mockReturnValue(
      createViewModel({
        activeDetail: {
          bars: [],
          indicators: null,
          timeframe: "5m",
          loading: false,
          loadingMoreBefore: false,
          hasMoreBefore: false,
          earliestLoadedAt: null,
          lookbackStartDate: null,
          nextFetchEndDate: null,
          error: null,
          updatedAt: null,
          source: "REST",
          barsDataSource: null
        }
      })
    );

    render(<TerminalMarketWatch />);

    expect(screen.getByText("Bars: -")).toBeTruthy();
  });

  it("shows delayed hint when latency is delayed", () => {
    useTerminalMarketWatchMock.mockReturnValue(
      createViewModel({
        dataLatency: "delayed",
        delayMinutes: 15
      })
    );

    render(<TerminalMarketWatch />);

    expect(screen.getAllByText("Delayed by 15 minutes").length).toBeGreaterThan(0);
  });
});
