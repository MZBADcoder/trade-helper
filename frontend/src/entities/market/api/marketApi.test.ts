import { afterEach, describe, expect, it, vi } from "vitest";

import { listMarketBars, listMarketBarsWithMeta } from "./marketApi";

describe("listMarketBarsWithMeta", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns bars and X-Data-Source header", async () => {
    const responseBars = [
      {
        ticker: "AAPL",
        timespan: "minute",
        multiplier: 5,
        start_at: "2026-02-18T14:30:00Z",
        open: 199.1,
        high: 201.4,
        low: 198.9,
        close: 200.8,
        volume: 32100
      }
    ];

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(responseBars), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "X-Data-Source": "DB_AGG_MIXED"
        }
      })
    );

    const payload = await listMarketBarsWithMeta({
      token: "token-1",
      ticker: "AAPL",
      timespan: "minute",
      multiplier: 5,
      from: "2026-02-04",
      to: "2026-02-18",
      limit: 2500
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, requestInit] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("/api/v1/market-data/bars?");
    expect(String(url)).toContain("ticker=AAPL");
    expect(String(url)).toContain("timespan=minute");
    expect(String(url)).toContain("multiplier=5");
    expect(String(url)).toContain("from=2026-02-04");
    expect(String(url)).toContain("to=2026-02-18");
    expect(String(url)).toContain("limit=2500");
    expect(requestInit?.method).toBe("GET");

    expect(payload.items).toEqual(responseBars);
    expect(payload.dataSource).toBe("DB_AGG_MIXED");
  });

  it("returns null when X-Data-Source is absent", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: {
          "Content-Type": "application/json"
        }
      })
    );

    const payload = await listMarketBarsWithMeta({
      token: "token-2",
      ticker: "NVDA"
    });

    expect(payload.items).toEqual([]);
    expect(payload.dataSource).toBeNull();
  });

  it("returns empty array when endpoint responds 204", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, {
        status: 204
      })
    );

    const payload = await listMarketBarsWithMeta({
      token: "token-3",
      ticker: "MSFT"
    });

    expect(payload.items).toEqual([]);
    expect(payload.dataSource).toBeNull();
  });
});

describe("listMarketBars", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns empty array when endpoint responds 204", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, {
        status: 204
      })
    );

    const payload = await listMarketBars({
      token: "token-4",
      ticker: "TSLA"
    });

    expect(payload).toEqual([]);
  });
});
