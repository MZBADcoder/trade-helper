import { describe, expect, it } from "vitest";

import {
  buildDetailCacheKey,
  marketQueryForTimeframe,
  mergeBarsByStartAt,
  isMarketStreamWindowOpen,
  resolveMarketRealtimeConfig,
  resolveStreamWsBaseUrl,
  sessionKeyForTimeframe,
  shouldIgnoreMarketMessage,
  shouldStopDegradedPollingOnStatus,
  streamChannelsForRealtime,
  websocketEnabledForDelay,
  TIMEFRAME_OPTIONS
} from "./marketWatchUtils";

describe("marketQueryForTimeframe", () => {
  it("maps intraday timeframes to 10-trading-day policy", () => {
    expect(marketQueryForTimeframe("1m")).toEqual({
      timespan: "minute",
      multiplier: 1,
      useTradingDays: true,
      lookbackDays: 10,
      initialWindowDays: 3,
      refreshWindowDays: 2,
      chunkWindowDays: 3,
      limit: 5000
    });
    expect(marketQueryForTimeframe("5m")).toEqual({
      timespan: "minute",
      multiplier: 5,
      useTradingDays: true,
      lookbackDays: 10,
      initialWindowDays: 10,
      refreshWindowDays: 2,
      chunkWindowDays: 10,
      limit: 1500
    });
    expect(marketQueryForTimeframe("15m")).toEqual({
      timespan: "minute",
      multiplier: 15,
      useTradingDays: true,
      lookbackDays: 10,
      initialWindowDays: 10,
      refreshWindowDays: 2,
      chunkWindowDays: 10,
      limit: 1000
    });
    expect(marketQueryForTimeframe("60m")).toEqual({
      timespan: "minute",
      multiplier: 60,
      useTradingDays: true,
      lookbackDays: 10,
      initialWindowDays: 10,
      refreshWindowDays: 3,
      chunkWindowDays: 10,
      limit: 500
    });
  });

  it("uses 10-year lookback for day/week/month", () => {
    expect(marketQueryForTimeframe("day")).toEqual({
      timespan: "day",
      multiplier: 1,
      useTradingDays: false,
      lookbackDays: 3650,
      initialWindowDays: 3650,
      refreshWindowDays: 60,
      chunkWindowDays: 3650,
      limit: 3000
    });
    expect(marketQueryForTimeframe("week")).toEqual({
      timespan: "week",
      multiplier: 1,
      useTradingDays: false,
      lookbackDays: 3650,
      initialWindowDays: 3650,
      refreshWindowDays: 180,
      chunkWindowDays: 3650,
      limit: 700
    });
    expect(marketQueryForTimeframe("month")).toEqual({
      timespan: "month",
      multiplier: 1,
      useTradingDays: false,
      lookbackDays: 3650,
      initialWindowDays: 3650,
      refreshWindowDays: 365,
      chunkWindowDays: 3650,
      limit: 240
    });
  });
});

describe("TIMEFRAME_OPTIONS", () => {
  it("contains 1m/5m/15m/60m and no legacy minute option", () => {
    const keys = TIMEFRAME_OPTIONS.map((item) => item.key);
    expect(keys).toEqual(["1m", "5m", "15m", "60m", "day", "week", "month"]);
    expect(keys).not.toContain("minute");
  });
});

describe("buildDetailCacheKey", () => {
  it("keeps session dimension for intraday timeframes", () => {
    expect(buildDetailCacheKey("AAPL", "5m", "regular")).not.toBe(buildDetailCacheKey("AAPL", "5m", "night"));
    expect(sessionKeyForTimeframe("5m", "night")).toBe("night");
  });

  it("ignores session dimension for non-intraday timeframes", () => {
    expect(buildDetailCacheKey("AAPL", "day", "regular")).toBe(buildDetailCacheKey("AAPL", "day", "night"));
    expect(buildDetailCacheKey("AAPL", "week", "pre")).toBe("AAPL::week");
    expect(sessionKeyForTimeframe("month", "night")).toBe("regular");
  });
});

describe("mergeBarsByStartAt", () => {
  it("deduplicates by start_at and keeps latest incoming value", () => {
    const merged = mergeBarsByStartAt(
      [
        {
          ticker: "AAPL",
          timespan: "minute",
          multiplier: 1,
          start_at: "2026-02-24T14:30:00Z",
          open: 100,
          high: 101,
          low: 99,
          close: 100,
          volume: 1000
        },
        {
          ticker: "AAPL",
          timespan: "minute",
          multiplier: 1,
          start_at: "2026-02-24T14:31:00Z",
          open: 101,
          high: 102,
          low: 100,
          close: 101,
          volume: 900
        }
      ],
      [
        {
          ticker: "AAPL",
          timespan: "minute",
          multiplier: 1,
          start_at: "2026-02-24T14:29:00Z",
          open: 99,
          high: 100,
          low: 98,
          close: 99,
          volume: 850
        },
        {
          ticker: "AAPL",
          timespan: "minute",
          multiplier: 1,
          start_at: "2026-02-24T14:30:00Z",
          open: 100.2,
          high: 101.3,
          low: 99.4,
          close: 100.6,
          volume: 1200
        }
      ]
    );

    expect(merged.map((item) => item.start_at)).toEqual([
      "2026-02-24T14:29:00Z",
      "2026-02-24T14:30:00Z",
      "2026-02-24T14:31:00Z"
    ]);
    expect(merged[1]?.open).toBe(100.2);
    expect(merged[1]?.volume).toBe(1200);
  });
});

describe("resolveMarketRealtimeConfig", () => {
  it("reads delay minutes from env-like values", () => {
    expect(
      resolveMarketRealtimeConfig({
        delayMinutes: "30"
      })
    ).toEqual({
      delayMinutes: 30
    });
  });

  it("falls back to defaults for invalid values", () => {
    expect(
      resolveMarketRealtimeConfig({
        delayMinutes: "-1"
      })
    ).toEqual({
      delayMinutes: 15
    });
  });

  it("accepts zero delay for realtime websocket mode", () => {
    expect(
      resolveMarketRealtimeConfig({
        delayMinutes: "0"
      })
    ).toEqual({
      delayMinutes: 0
    });
  });

  it("rejects non-digit delay formats", () => {
    expect(
      resolveMarketRealtimeConfig({
        delayMinutes: "1e2"
      })
    ).toEqual({
      delayMinutes: 15
    });

    expect(
      resolveMarketRealtimeConfig({
        delayMinutes: "15m"
      })
    ).toEqual({
      delayMinutes: 15
    });
  });
});

describe("websocketEnabledForDelay", () => {
  it("enables websocket only when delay is zero", () => {
    expect(websocketEnabledForDelay(0)).toBe(true);
    expect(websocketEnabledForDelay(15)).toBe(false);
  });
});

describe("resolveStreamWsBaseUrl", () => {
  it("uses explicit websocket base url when provided", () => {
    expect(
      resolveStreamWsBaseUrl({
        wsBaseUrl: "wss://stream.example.com"
      })
    ).toBe("wss://stream.example.com");
  });

  it("converts api base url to websocket protocol", () => {
    expect(
      resolveStreamWsBaseUrl({
        apiBaseUrl: "http://127.0.0.1:8000"
      })
    ).toBe("ws://127.0.0.1:8000");
  });

  it("supports host:port base without protocol", () => {
    expect(
      resolveStreamWsBaseUrl({
        wsBaseUrl: "localhost:9000"
      })
    ).toBe("ws://localhost:9000");
  });

  it("falls back to current origin when env values are invalid", () => {
    const expectedProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    expect(
      resolveStreamWsBaseUrl({
        wsBaseUrl: "::invalid::",
        apiBaseUrl: "::invalid::"
      })
    ).toBe(`${expectedProtocol}//${window.location.host}`);
  });
});

describe("streamChannelsForRealtime", () => {
  it("always keeps the same stream channels", () => {
    expect(streamChannelsForRealtime()).toEqual(["trade", "quote", "aggregate"]);
  });
});

describe("shouldIgnoreMarketMessage", () => {
  it("does not ignore quote messages", () => {
    expect(
      shouldIgnoreMarketMessage(
        {
          type: "market.quote",
          symbol: "AAPL",
          eventTs: "2026-02-19T12:00:01Z",
          bid: 203.11,
          ask: 203.12,
          bidSize: 10,
          askSize: 9
        }
      )
    ).toBe(false);

    expect(
      shouldIgnoreMarketMessage(
        {
          type: "market.trade",
          symbol: "AAPL",
          eventTs: "2026-02-19T12:00:01Z",
          price: 203.11,
          last: 203.11,
          size: 10
        }
      )
    ).toBe(false);
  });
});

describe("shouldStopDegradedPollingOnStatus", () => {
  it("stops degraded polling when stream reports connected", () => {
    expect(
      shouldStopDegradedPollingOnStatus(
        {
          type: "system.status",
          latency: "delayed",
          connectionState: "connected",
          message: "ok"
        }
      )
    ).toBe(true);
  });

  it("does not stop degraded polling when stream is reconnecting", () => {
    expect(
      shouldStopDegradedPollingOnStatus(
        {
          type: "system.status",
          latency: "real-time",
          connectionState: "reconnecting",
          message: null
        }
      )
    ).toBe(false);
  });

  it("does not stop degraded polling when connection_state is missing", () => {
    expect(
      shouldStopDegradedPollingOnStatus(
        {
          type: "system.status",
          latency: "delayed",
          connectionState: null,
          message: null
        }
      )
    ).toBe(false);
  });
});

describe("isMarketStreamWindowOpen", () => {
  it("uses delayed clock to decide stream window", () => {
    expect(
      isMarketStreamWindowOpen({
        delayMinutes: 15,
        nowMs: Date.parse("2026-02-24T14:40:00Z")
      })
    ).toBe(false);

    expect(
      isMarketStreamWindowOpen({
        delayMinutes: 15,
        nowMs: Date.parse("2026-02-24T14:50:00Z")
      })
    ).toBe(true);
  });

  it("returns false on weekends", () => {
    expect(
      isMarketStreamWindowOpen({
        delayMinutes: 15,
        nowMs: Date.parse("2026-02-22T16:00:00Z")
      })
    ).toBe(false);
  });
});
