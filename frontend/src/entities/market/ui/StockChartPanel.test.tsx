import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { buildIndicators } from "../model/indicators";
import { type MarketBar } from "../model/types";
import { StockChartPanel } from "./StockChartPanel";

function createBars(count: number): MarketBar[] {
  const start = Date.parse("2026-02-24T14:30:00Z");
  const bars: MarketBar[] = [];

  for (let index = 0; index < count; index += 1) {
    const time = new Date(start + index * 60_000).toISOString();
    const price = 100 + index * 0.05;

    bars.push({
      ticker: "AAPL",
      timespan: "minute",
      multiplier: 1,
      start_at: time,
      open: price,
      high: price + 0.5,
      low: price - 0.5,
      close: price + 0.2,
      volume: 1_000 + index
    });
  }

  return bars;
}

describe("StockChartPanel", () => {
  it("renders chart when only one bar is available", () => {
    const bars = createBars(1);
    const indicators = buildIndicators(bars);

    const { unmount } = render(<StockChartPanel ticker="AAPL" timeframe="1m" bars={bars} indicators={indicators} />);

    expect(screen.getByText("AAPL Price / MA / BOLL")).toBeTruthy();
    expect(screen.getByText("Bars 1")).toBeTruthy();
    expect(screen.queryByText("Insufficient bars for chart rendering.")).toBeNull();

    unmount();
  });

  it("supports + / - zoom levels", () => {
    const bars = createBars(1200);
    const indicators = buildIndicators(bars);

    render(<StockChartPanel ticker="AAPL" timeframe="1m" bars={bars} indicators={indicators} />);

    expect(screen.getByText("Bars 300")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "+" }));
    expect(screen.getByText("Bars 500")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "+" }));
    expect(screen.getByText("Bars 1000")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "-" }));
    expect(screen.getByText("Bars 500")).toBeTruthy();
  });

  it("triggers auto history load when panned to the left edge", async () => {
    const bars = createBars(1200);
    const indicators = buildIndicators(bars);
    const loadMore = vi.fn(async () => undefined);

    const { container } = render(
      <StockChartPanel
        ticker="AAPL"
        timeframe="1m"
        bars={bars}
        indicators={indicators}
        hasMoreBefore
        onLoadMoreBefore={loadMore}
      />
    );

    const svg = container.querySelector("svg.chartSvgInteractive");
    if (!svg) {
      throw new Error("chart svg not found");
    }

    fireEvent.pointerDown(svg, { pointerId: 1, clientX: 600, clientY: 80 });
    fireEvent.pointerMove(svg, { pointerId: 1, clientX: -120, clientY: 80 });
    fireEvent.pointerUp(svg, { pointerId: 1, clientX: -120, clientY: 80 });

    await waitFor(() => {
      expect(loadMore).toHaveBeenCalledTimes(1);
    });
  });

  it("re-triggers auto load when history cursor advances with same bars", async () => {
    const bars = createBars(1200);
    const indicators = buildIndicators(bars);
    const loadMore = vi.fn(async () => undefined);

    const { container, rerender } = render(
      <StockChartPanel
        ticker="AAPL"
        timeframe="1m"
        historyCursor="2026-02-24"
        bars={bars}
        indicators={indicators}
        hasMoreBefore
        onLoadMoreBefore={loadMore}
      />
    );

    const svg = container.querySelector("svg.chartSvgInteractive");
    if (!svg) {
      throw new Error("chart svg not found");
    }

    fireEvent.pointerDown(svg, { pointerId: 1, clientX: 600, clientY: 80 });
    fireEvent.pointerMove(svg, { pointerId: 1, clientX: -120, clientY: 80 });
    fireEvent.pointerUp(svg, { pointerId: 1, clientX: -120, clientY: 80 });

    await waitFor(() => {
      expect(loadMore).toHaveBeenCalledTimes(1);
    });

    rerender(
      <StockChartPanel
        ticker="AAPL"
        timeframe="1m"
        historyCursor="2026-02-23"
        bars={bars}
        indicators={indicators}
        hasMoreBefore
        onLoadMoreBefore={loadMore}
      />
    );

    await waitFor(() => {
      expect(loadMore).toHaveBeenCalledTimes(2);
    });
  });
});
