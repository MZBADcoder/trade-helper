import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type MarketBar } from "@/entities/market";

const {
  addWatchlistMock,
  deleteWatchlistMock,
  listMarketBarsWithMetaMock,
  listMarketSnapshotsMock,
  listTradingDaysMock,
  listWatchlistMock
} = vi.hoisted(() => ({
  listMarketBarsWithMetaMock: vi.fn(),
  listMarketSnapshotsMock: vi.fn(),
  listTradingDaysMock: vi.fn(),
  listWatchlistMock: vi.fn(),
  addWatchlistMock: vi.fn(),
  deleteWatchlistMock: vi.fn()
}));

vi.mock("@/entities/session", () => ({
  useSession: () => ({
    token: "test-token",
    user: {
      email: "trader@test.dev"
    }
  })
}));

vi.mock("@/entities/watchlist", () => ({
  listWatchlist: listWatchlistMock,
  addWatchlist: addWatchlistMock,
  deleteWatchlist: deleteWatchlistMock
}));

vi.mock("@/entities/market", async () => {
  const actual = await vi.importActual<typeof import("@/entities/market")>("@/entities/market");
  return {
    ...actual,
    listMarketBarsWithMeta: listMarketBarsWithMetaMock,
    listMarketSnapshots: listMarketSnapshotsMock,
    listTradingDays: listTradingDaysMock
  };
});

import { useTerminalMarketWatch } from "./useTerminalMarketWatch";

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function createBar(startAt: string, close: number): MarketBar {
  return {
    ticker: "AAPL",
    timespan: "minute",
    multiplier: 1,
    start_at: startAt,
    open: close - 0.1,
    high: close + 0.2,
    low: close - 0.3,
    close,
    volume: 1000
  };
}

beforeEach(() => {
  vi.clearAllMocks();

  listWatchlistMock.mockResolvedValue([{ ticker: "AAPL" }]);
  listMarketSnapshotsMock.mockResolvedValue([]);
  listTradingDaysMock.mockResolvedValue(["2026-02-24"]);
  addWatchlistMock.mockResolvedValue(undefined);
  deleteWatchlistMock.mockResolvedValue(undefined);
});

describe("useTerminalMarketWatch force-refresh concurrency", () => {
  it("keeps first intraday force response when a second force refresh is skipped", async () => {
    const firstRequest = createDeferred<{ items: MarketBar[]; dataSource: string | null }>();
    listMarketBarsWithMetaMock.mockReturnValueOnce(firstRequest.promise);

    const { result } = renderHook(() => useTerminalMarketWatch());

    await waitFor(() => {
      expect(result.current.activeTicker).toBe("AAPL");
    });
    await waitFor(() => {
      expect(listMarketBarsWithMetaMock).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      await result.current.loadTickerDetail("AAPL", true);
    });
    expect(listMarketBarsWithMetaMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      firstRequest.resolve({
        items: [createBar("2026-02-24T14:30:00Z", 101.2)],
        dataSource: "DB_AGG_MIXED"
      });
      await firstRequest.promise;
    });

    await waitFor(() => {
      expect(result.current.activeDetail?.bars.length).toBe(1);
    });
    expect(result.current.activeDetail?.bars[0]?.close).toBe(101.2);
  });

  it("deduplicates force refreshes for non-intraday kline timeframe", async () => {
    const klineRequest = createDeferred<{ items: MarketBar[]; dataSource: string | null }>();

    listMarketBarsWithMetaMock
      .mockResolvedValueOnce({
        items: [createBar("2026-02-24T14:30:00Z", 100.1)],
        dataSource: "DB_AGG_MIXED"
      })
      .mockReturnValueOnce(klineRequest.promise);

    const { result } = renderHook(() => useTerminalMarketWatch());

    await waitFor(() => {
      expect(result.current.activeTicker).toBe("AAPL");
    });
    await waitFor(() => {
      expect(result.current.activeDetail?.bars.length).toBe(1);
    });

    act(() => {
      result.current.setTimeframe("1m");
    });

    await waitFor(() => {
      expect(listMarketBarsWithMetaMock).toHaveBeenCalledTimes(2);
    });

    await act(async () => {
      await result.current.loadTickerDetail("AAPL", true);
    });
    expect(listMarketBarsWithMetaMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      klineRequest.resolve({
        items: [createBar("2026-02-24T14:31:00Z", 102.3)],
        dataSource: "DB_AGG_MIXED"
      });
      await klineRequest.promise;
    });

    await waitFor(() => {
      expect(result.current.activeDetail?.timeframe).toBe("1m");
    });
    expect(result.current.activeDetail?.bars[0]?.close).toBe(102.3);
  });
});
