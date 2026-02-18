import { describe, expect, it } from "vitest";

import { marketQueryForTimeframe, TIMEFRAME_OPTIONS } from "./useTerminalMarketWatch";

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
