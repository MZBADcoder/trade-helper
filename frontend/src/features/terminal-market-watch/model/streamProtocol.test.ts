import { describe, expect, it } from "vitest";

import { parseStreamEnvelope } from "./streamProtocol";

describe("parseStreamEnvelope", () => {
  it("parses system.status envelope from backend contract", () => {
    const parsed = parseStreamEnvelope(
      JSON.stringify({
        type: "system.status",
        ts: "2026-02-19T12:00:00Z",
        source: "WS",
        data: {
          latency: "real-time",
          connection_state: "connected",
          message: "ok"
        }
      })
    );

    expect(parsed).toEqual({
      type: "system.status",
      latency: "real-time",
      connectionState: "connected",
      message: "ok"
    });
  });

  it("parses market.quote envelope with symbol and event timestamp", () => {
    const parsed = parseStreamEnvelope(
      JSON.stringify({
        type: "market.quote",
        ts: "2026-02-19T12:00:01Z",
        source: "WS",
        data: {
          symbol: "aapl",
          event_ts: "2026-02-19T12:00:01Z",
          bid: 203.11,
          ask: 203.12,
          bid_size: 10,
          ask_size: 9
        }
      })
    );

    expect(parsed).toEqual({
      type: "market.quote",
      symbol: "AAPL",
      eventTs: "2026-02-19T12:00:01Z",
      bid: 203.11,
      ask: 203.12,
      bidSize: 10,
      askSize: 9
    });
  });

  it("returns null for unsupported or malformed payload", () => {
    expect(parseStreamEnvelope("not-json")).toBeNull();
    expect(parseStreamEnvelope(JSON.stringify({ type: "unknown", data: {} }))).toBeNull();
    expect(parseStreamEnvelope(JSON.stringify({ type: "market.trade", data: {} }))).toBeNull();
  });
});
