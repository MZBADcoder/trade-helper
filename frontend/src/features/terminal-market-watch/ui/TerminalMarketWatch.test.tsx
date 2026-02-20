import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { type TerminalMarketWatchViewModel } from "../model/types";

const { useTerminalMarketWatchMock } = vi.hoisted(() => ({
  useTerminalMarketWatchMock: vi.fn()
}));

vi.mock("../model/useTerminalMarketWatch", () => ({
  TIMEFRAME_OPTIONS: [
    { key: "5m", label: "5m" },
    { key: "15m", label: "15m" },
    { key: "60m", label: "60m" },
    { key: "day", label: "Day" },
    { key: "week", label: "Week" },
    { key: "month", label: "Month" }
  ],
  useTerminalMarketWatch: useTerminalMarketWatchMock
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
    activeDetail: {
      bars: [],
      indicators: null,
      timeframe: "5m",
      loading: false,
      error: null,
      updatedAt: null,
      source: "REST",
      barsDataSource: "DB_AGG_MIXED"
    },
    activeSnapshot: null,
    latestBar: undefined,
    loadTickerDetail: vi.fn(async () => undefined),
    refreshSnapshots: vi.fn(async () => undefined),
    streamStatus: "connected",
    streamSource: "REST",
    dataLatency: "delayed",
    realtimeEnabled: true,
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

  it("shows delayed hint when realtime is disabled", () => {
    useTerminalMarketWatchMock.mockReturnValue(
      createViewModel({
        realtimeEnabled: false,
        delayMinutes: 15
      })
    );

    render(<TerminalMarketWatch />);

    expect(screen.getAllByText("Delayed by 15 minutes").length).toBeGreaterThan(0);
  });
});
