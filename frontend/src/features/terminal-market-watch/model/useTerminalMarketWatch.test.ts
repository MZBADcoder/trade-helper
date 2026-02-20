import { describe, expect, it } from "vitest";

import {
  marketQueryForTimeframe,
  resolveMarketRealtimeConfig,
  shouldIgnoreMarketMessage,
  shouldStopDegradedPollingOnStatus,
  streamChannelsForRealtime,
  TIMEFRAME_OPTIONS
} from "./useTerminalMarketWatch";

describe("marketQueryForTimeframe", () => {
  it("maps BE-0005 minute timeframes to supported multipliers", () => {
    expect(marketQueryForTimeframe("5m")).toEqual({
      timespan: "minute",
      multiplier: 5,
      fromDays: -14,
      limit: 2500
    });
    expect(marketQueryForTimeframe("15m")).toEqual({
      timespan: "minute",
      multiplier: 15,
      fromDays: -14,
      limit: 1200
    });
    expect(marketQueryForTimeframe("60m")).toEqual({
      timespan: "minute",
      multiplier: 60,
      fromDays: -14,
      limit: 520
    });
  });

  it("keeps existing day/week/month mappings", () => {
    expect(marketQueryForTimeframe("day")).toEqual({
      timespan: "day",
      multiplier: 1,
      fromDays: -320,
      limit: 900
    });
    expect(marketQueryForTimeframe("week")).toEqual({
      timespan: "week",
      multiplier: 1,
      fromDays: -3650,
      limit: 700
    });
    expect(marketQueryForTimeframe("month")).toEqual({
      timespan: "month",
      multiplier: 1,
      fromDays: -7300,
      limit: 360
    });
  });
});

describe("TIMEFRAME_OPTIONS", () => {
  it("contains 5m/15m/60m and no legacy minute option", () => {
    const keys = TIMEFRAME_OPTIONS.map((item) => item.key);
    expect(keys).toEqual(["5m", "15m", "60m", "day", "week", "month"]);
    expect(keys).not.toContain("minute");
  });
});

describe("resolveMarketRealtimeConfig", () => {
  it("reads realtime enabled and delay minutes from env-like values", () => {
    expect(
      resolveMarketRealtimeConfig({
        realtimeEnabled: "true",
        delayMinutes: "30"
      })
    ).toEqual({
      realtimeEnabled: true,
      delayMinutes: 30
    });
  });

  it("falls back to defaults for invalid values", () => {
    expect(
      resolveMarketRealtimeConfig({
        realtimeEnabled: "invalid",
        delayMinutes: "-1"
      })
    ).toEqual({
      realtimeEnabled: true,
      delayMinutes: 15
    });
  });

  it("rejects non-digit delay formats", () => {
    expect(
      resolveMarketRealtimeConfig({
        realtimeEnabled: "true",
        delayMinutes: "1e2"
      })
    ).toEqual({
      realtimeEnabled: true,
      delayMinutes: 15
    });

    expect(
      resolveMarketRealtimeConfig({
        realtimeEnabled: "true",
        delayMinutes: "15m"
      })
    ).toEqual({
      realtimeEnabled: true,
      delayMinutes: 15
    });
  });
});

describe("streamChannelsForRealtime", () => {
  it("excludes quote channel in delayed mode", () => {
    expect(streamChannelsForRealtime(true)).toEqual(["trade", "quote", "aggregate"]);
    expect(streamChannelsForRealtime(false)).toEqual(["trade", "aggregate"]);
  });
});

describe("shouldIgnoreMarketMessage", () => {
  it("ignores quote messages when realtime is disabled", () => {
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
        },
        false
      )
    ).toBe(true);

    expect(
      shouldIgnoreMarketMessage(
        {
          type: "market.trade",
          symbol: "AAPL",
          eventTs: "2026-02-19T12:00:01Z",
          price: 203.11,
          last: 203.11,
          size: 10
        },
        false
      )
    ).toBe(false);
  });
});

describe("shouldStopDegradedPollingOnStatus", () => {
  it("stops degraded polling when delayed mode reconnects", () => {
    expect(
      shouldStopDegradedPollingOnStatus(
        {
          type: "system.status",
          latency: "real-time",
          connectionState: "connected",
          message: "ok"
        },
        false
      )
    ).toBe(true);
  });

  it("does not stop degraded polling when delayed mode is not connected", () => {
    expect(
      shouldStopDegradedPollingOnStatus(
        {
          type: "system.status",
          latency: "real-time",
          connectionState: "reconnecting",
          message: null
        },
        false
      )
    ).toBe(false);
  });
});
