import React from "react";

import { type IndicatorBundle, type MarketBar } from "@/entities/market";

type StockChartPanelProps = {
  ticker: string;
  bars: MarketBar[];
  indicators: IndicatorBundle;
};

const PRICE_WIDTH = 960;
const PANE_PADDING = 16;

export function StockChartPanel({ ticker, bars, indicators }: StockChartPanelProps) {
  const visibleCount = 90;
  const visibleBars = bars.slice(-visibleCount);
  const offset = Math.max(0, bars.length - visibleBars.length);

  const ma20 = indicators.ma20.slice(offset);
  const ma50 = indicators.ma50.slice(offset);
  const bollUpper = indicators.bollUpper.slice(offset);
  const bollLower = indicators.bollLower.slice(offset);
  const macdLine = indicators.macdLine.slice(offset);
  const macdSignal = indicators.macdSignal.slice(offset);
  const macdHistogram = indicators.macdHistogram.slice(offset);
  const rsi14 = indicators.rsi14.slice(offset);

  if (visibleBars.length < 2) {
    return <div className="muted">Insufficient bars for chart rendering.</div>;
  }

  return (
    <div className="chartStack">
      <PricePane
        ticker={ticker}
        bars={visibleBars}
        ma20={ma20}
        ma50={ma50}
        bollUpper={bollUpper}
        bollLower={bollLower}
      />
      <MacdPane line={macdLine} signal={macdSignal} histogram={macdHistogram} />
      <RsiPane values={rsi14} />
      <VolumePane bars={visibleBars} />
    </div>
  );
}

type PricePaneProps = {
  ticker: string;
  bars: MarketBar[];
  ma20: Array<number | null>;
  ma50: Array<number | null>;
  bollUpper: Array<number | null>;
  bollLower: Array<number | null>;
};

function PricePane({ ticker, bars, ma20, ma50, bollUpper, bollLower }: PricePaneProps) {
  const width = PRICE_WIDTH;
  const height = 300;
  const stepX = (width - PANE_PADDING * 2) / bars.length;

  const priceMax = Math.max(...bars.map((bar) => bar.high));
  const priceMin = Math.min(...bars.map((bar) => bar.low));
  const y = (value: number) => scaleValue(value, priceMin, priceMax, height);

  const upperPath = buildLinePath(bollUpper, stepX, (value) => y(value), width);
  const lowerPath = buildLinePath(bollLower, stepX, (value) => y(value), width);
  const ma20Path = buildLinePath(ma20, stepX, (value) => y(value), width);
  const ma50Path = buildLinePath(ma50, stepX, (value) => y(value), width);

  return (
    <section className="chartPanel">
      <div className="chartHeader">
        <span className="chartTitle">{ticker} Price / MA / BOLL</span>
      </div>
      <svg className="chartSvg" viewBox={`0 0 ${width} ${height}`}>
        <rect x="0" y="0" width={width} height={height} fill="rgba(5, 10, 18, 0.85)" />
        <line x1={PANE_PADDING} y1={height - PANE_PADDING} x2={width - PANE_PADDING} y2={height - PANE_PADDING} stroke="rgba(200, 210, 230, 0.16)" />

        {bars.map((bar, index) => {
          const x = PANE_PADDING + index * stepX + stepX * 0.5;
          const openY = y(bar.open);
          const closeY = y(bar.close);
          const highY = y(bar.high);
          const lowY = y(bar.low);
          const isBull = bar.close >= bar.open;
          const bodyY = Math.min(openY, closeY);
          const bodyHeight = Math.max(1, Math.abs(openY - closeY));
          const bodyWidth = Math.max(1, stepX * 0.58);

          return (
            <g key={`${bar.start_at}-${index}`}>
              <line x1={x} x2={x} y1={highY} y2={lowY} stroke={isBull ? "#63d9b4" : "#ff5e7e"} strokeWidth="1" />
              <rect
                x={x - bodyWidth / 2}
                y={bodyY}
                width={bodyWidth}
                height={bodyHeight}
                fill={isBull ? "rgba(99, 217, 180, 0.85)" : "rgba(255, 94, 126, 0.88)"}
              />
            </g>
          );
        })}

        <path d={upperPath} stroke="#5c8cf7" strokeWidth="1.2" fill="none" opacity="0.8" />
        <path d={lowerPath} stroke="#5c8cf7" strokeWidth="1.2" fill="none" opacity="0.8" />
        <path d={ma20Path} stroke="#f9d66b" strokeWidth="1.5" fill="none" />
        <path d={ma50Path} stroke="#ef8ea7" strokeWidth="1.5" fill="none" />
      </svg>
    </section>
  );
}

type MacdPaneProps = {
  line: Array<number | null>;
  signal: Array<number | null>;
  histogram: Array<number | null>;
};

function MacdPane({ line, signal, histogram }: MacdPaneProps) {
  const width = PRICE_WIDTH;
  const height = 148;
  const stepX = (width - PANE_PADDING * 2) / histogram.length;

  const values = [...line, ...signal, ...histogram].filter((value): value is number => value !== null);
  const max = values.length ? Math.max(...values) : 1;
  const min = values.length ? Math.min(...values) : -1;
  const domainMin = Math.min(min, 0);
  const domainMax = Math.max(max, 0);
  const y = (value: number) => scaleValue(value, domainMin, domainMax, height);
  const zeroY = y(0);

  const macdPath = buildLinePath(line, stepX, (value) => y(value), width);
  const signalPath = buildLinePath(signal, stepX, (value) => y(value), width);

  return (
    <section className="chartPanel">
      <div className="chartHeader">
        <span className="chartTitle">MACD (12,26,9)</span>
      </div>
      <svg className="chartSvg" viewBox={`0 0 ${width} ${height}`}>
        <rect x="0" y="0" width={width} height={height} fill="rgba(5, 10, 18, 0.85)" />
        <line x1={PANE_PADDING} y1={zeroY} x2={width - PANE_PADDING} y2={zeroY} stroke="rgba(200, 210, 230, 0.25)" strokeDasharray="3 3" />

        {histogram.map((value, index) => {
          if (value === null) return null;
          const x = PANE_PADDING + index * stepX + stepX * 0.2;
          const yValue = y(value);
          const barHeight = Math.max(1, Math.abs(yValue - zeroY));
          return (
            <rect
              key={index}
              x={x}
              y={Math.min(yValue, zeroY)}
              width={Math.max(1, stepX * 0.6)}
              height={barHeight}
              fill={value >= 0 ? "rgba(99, 217, 180, 0.8)" : "rgba(255, 94, 126, 0.8)"}
            />
          );
        })}

        <path d={macdPath} stroke="#7cc6ff" strokeWidth="1.5" fill="none" />
        <path d={signalPath} stroke="#ffd36a" strokeWidth="1.5" fill="none" />
      </svg>
    </section>
  );
}

function RsiPane({ values }: { values: Array<number | null> }) {
  const width = PRICE_WIDTH;
  const height = 132;
  const stepX = (width - PANE_PADDING * 2) / values.length;

  const y = (value: number) => scaleValue(value, 0, 100, height);
  const rsiPath = buildLinePath(values, stepX, (value) => y(value), width);

  return (
    <section className="chartPanel">
      <div className="chartHeader">
        <span className="chartTitle">RSI (14)</span>
      </div>
      <svg className="chartSvg" viewBox={`0 0 ${width} ${height}`}>
        <rect x="0" y="0" width={width} height={height} fill="rgba(5, 10, 18, 0.85)" />
        <line x1={PANE_PADDING} y1={y(70)} x2={width - PANE_PADDING} y2={y(70)} stroke="rgba(255, 102, 133, 0.45)" strokeDasharray="4 4" />
        <line x1={PANE_PADDING} y1={y(30)} x2={width - PANE_PADDING} y2={y(30)} stroke="rgba(111, 237, 176, 0.45)" strokeDasharray="4 4" />
        <path d={rsiPath} stroke="#84b5ff" strokeWidth="1.5" fill="none" />
      </svg>
    </section>
  );
}

function VolumePane({ bars }: { bars: MarketBar[] }) {
  const width = PRICE_WIDTH;
  const height = 130;
  const stepX = (width - PANE_PADDING * 2) / bars.length;
  const maxVolume = Math.max(...bars.map((bar) => bar.volume), 1);

  return (
    <section className="chartPanel">
      <div className="chartHeader">
        <span className="chartTitle">VOL</span>
      </div>
      <svg className="chartSvg" viewBox={`0 0 ${width} ${height}`}>
        <rect x="0" y="0" width={width} height={height} fill="rgba(5, 10, 18, 0.85)" />
        {bars.map((bar, index) => {
          const x = PANE_PADDING + index * stepX + stepX * 0.2;
          const barHeight = Math.max(1, (bar.volume / maxVolume) * (height - PANE_PADDING * 2));
          const y = height - PANE_PADDING - barHeight;
          const bullish = bar.close >= bar.open;
          return (
            <rect
              key={`${bar.start_at}-${index}`}
              x={x}
              y={y}
              width={Math.max(1, stepX * 0.6)}
              height={barHeight}
              fill={bullish ? "rgba(99, 217, 180, 0.85)" : "rgba(255, 94, 126, 0.85)"}
            />
          );
        })}
      </svg>
    </section>
  );
}

function scaleValue(value: number, min: number, max: number, height: number): number {
  const top = PANE_PADDING;
  const bottom = height - PANE_PADDING;
  if (max - min === 0) return (top + bottom) / 2;
  const ratio = (value - min) / (max - min);
  return bottom - ratio * (bottom - top);
}

function buildLinePath(
  values: Array<number | null>,
  stepX: number,
  yMapper: (value: number) => number,
  width: number
): string {
  const commands: string[] = [];
  let drawing = false;

  values.forEach((value, index) => {
    if (value === null) {
      drawing = false;
      return;
    }

    const x = Math.min(width - PANE_PADDING, PANE_PADDING + index * stepX + stepX * 0.5);
    const y = yMapper(value);

    if (!drawing) {
      commands.push(`M ${x.toFixed(2)} ${y.toFixed(2)}`);
      drawing = true;
      return;
    }

    commands.push(`L ${x.toFixed(2)} ${y.toFixed(2)}`);
  });

  return commands.join(" ");
}
