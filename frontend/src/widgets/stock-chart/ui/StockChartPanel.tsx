import React from "react";

import { type IndicatorBundle, type MarketBar } from "@/entities/market";

type StockChartPanelProps = {
  ticker: string;
  bars: MarketBar[];
  indicators: IndicatorBundle;
};

const CHART_WIDTH = 960;
const PLOT_LEFT = 16;
const PLOT_RIGHT = 72;
const PLOT_TOP_BOTTOM = 16;

export function StockChartPanel({ ticker, bars, indicators }: StockChartPanelProps) {
  const visibleCount = 90;
  const visibleBars = bars.slice(-visibleCount);
  const offset = Math.max(0, bars.length - visibleBars.length);

  const ma20 = indicators.ma20.slice(offset);
  const ma50 = indicators.ma50.slice(offset);
  const bollMid = indicators.bollMid.slice(offset);
  const bollUpper = indicators.bollUpper.slice(offset);
  const bollLower = indicators.bollLower.slice(offset);
  const macdLine = indicators.macdLine.slice(offset);
  const macdSignal = indicators.macdSignal.slice(offset);
  const macdHistogram = indicators.macdHistogram.slice(offset);
  const rsi14 = indicators.rsi14.slice(offset);
  const volumeMa5 = simpleMovingAverage(visibleBars.map((bar) => bar.volume), 5);
  const labels = visibleBars.map((bar) => bar.start_at);
  const timeTicks = buildTimeTicks(visibleBars, 6);

  const [hoveredIndex, setHoveredIndex] = React.useState<number | null>(null);
  const [showMa20, setShowMa20] = React.useState(true);
  const [showMa50, setShowMa50] = React.useState(true);
  const [showBoll, setShowBoll] = React.useState(true);

  React.useEffect(() => {
    setHoveredIndex(null);
  }, [bars]);

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
        bollMid={bollMid}
        bollUpper={bollUpper}
        bollLower={bollLower}
        hoverIndex={hoveredIndex}
        onHoverChange={setHoveredIndex}
        showMa20={showMa20}
        showMa50={showMa50}
        showBoll={showBoll}
        onToggleMa20={() => setShowMa20((prev) => !prev)}
        onToggleMa50={() => setShowMa50((prev) => !prev)}
        onToggleBoll={() => setShowBoll((prev) => !prev)}
      />
      <MacdPane
        line={macdLine}
        signal={macdSignal}
        histogram={macdHistogram}
        labels={labels}
        hoverIndex={hoveredIndex}
        onHoverChange={setHoveredIndex}
      />
      <RsiPane values={rsi14} labels={labels} hoverIndex={hoveredIndex} onHoverChange={setHoveredIndex} />
      <VolumePane
        bars={visibleBars}
        volumeMa5={volumeMa5}
        hoverIndex={hoveredIndex}
        onHoverChange={setHoveredIndex}
        timeTicks={timeTicks}
      />
    </div>
  );
}

type PricePaneProps = {
  ticker: string;
  bars: MarketBar[];
  ma20: Array<number | null>;
  ma50: Array<number | null>;
  bollMid: Array<number | null>;
  bollUpper: Array<number | null>;
  bollLower: Array<number | null>;
  hoverIndex: number | null;
  onHoverChange: (index: number | null) => void;
  showMa20: boolean;
  showMa50: boolean;
  showBoll: boolean;
  onToggleMa20: () => void;
  onToggleMa50: () => void;
  onToggleBoll: () => void;
};

function PricePane({
  ticker,
  bars,
  ma20,
  ma50,
  bollMid,
  bollUpper,
  bollLower,
  hoverIndex,
  onHoverChange,
  showMa20,
  showMa50,
  showBoll,
  onToggleMa20,
  onToggleMa50,
  onToggleBoll
}: PricePaneProps) {
  const width = CHART_WIDTH;
  const height = 310;
  const plotWidth = width - PLOT_LEFT - PLOT_RIGHT;
  const stepX = plotWidth / bars.length;

  const activeIndex = hoverIndex ?? bars.length - 1;
  const activeBar = bars[activeIndex];

  const range = collectPriceRange(bars, ma20, ma50, bollUpper, bollLower);
  const y = (value: number) => scaleValue(value, range.min, range.max, height);

  const axisTicks = getLinearTicks(range.min, range.max, 5);

  const upperPath = buildLinePath(bollUpper, stepX, (value) => y(value), width);
  const lowerPath = buildLinePath(bollLower, stepX, (value) => y(value), width);
  const ma20Path = buildLinePath(ma20, stepX, (value) => y(value), width);
  const ma50Path = buildLinePath(ma50, stepX, (value) => y(value), width);

  const crossX = indexToX(activeIndex, stepX);
  const closeY = y(activeBar.close);

  const tooltipWidth = 210;
  const tooltipHeight = 136;
  const tooltipX = Math.min(width - tooltipWidth - 10, Math.max(10, crossX + 12));
  const tooltipY = Math.min(height - tooltipHeight - 10, Math.max(10, closeY - tooltipHeight / 2));

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const x = pointerToChartX(event, width);
    onHoverChange(coordinateToIndex(x, stepX, bars.length));
  }

  return (
    <section className="chartPanel">
      <div className="chartHeader chartHeaderSplit">
        <div className="chartTitleRow">
          <span className="chartTitle">{ticker} Price / MA / BOLL</span>
          <InfoHint
            title="Price / MA / BOLL"
            content="MA20/MA50 是收盘价移动平均线。BOLL 中轨=MA20，上轨/下轨=MA20 ± 2×标准差，用于观察趋势与波动区间。"
          />
        </div>
        <div className="chartHeaderControls">
          <div className="chartToggleGroup">
            <button type="button" className={`chartToggleBtn ${showMa20 ? "chartToggleBtnActive" : ""}`} onClick={onToggleMa20}>
              <span className="chartToggleSwatch chartToggleSwatchMa20" />
              MA20
            </button>
            <button type="button" className={`chartToggleBtn ${showMa50 ? "chartToggleBtnActive" : ""}`} onClick={onToggleMa50}>
              <span className="chartToggleSwatch chartToggleSwatchMa50" />
              MA50
            </button>
            <button type="button" className={`chartToggleBtn ${showBoll ? "chartToggleBtnActive" : ""}`} onClick={onToggleBoll}>
              <span className="chartToggleSwatch chartToggleSwatchBoll" />
              BOLL
            </button>
          </div>
          <div className="chartIndicatorRow">
            <span className="chartIndicatorTag">{formatDate(activeBar.start_at)}</span>
            <span className="chartIndicatorTag">Price {toPrice(activeBar.close)}</span>
            <span className="chartIndicatorTag">MA20 {toPrice(ma20[activeIndex])}</span>
            <span className="chartIndicatorTag">MA50 {toPrice(ma50[activeIndex])}</span>
            <span className="chartIndicatorTag">BOLL U {toPrice(bollUpper[activeIndex])}</span>
            <span className="chartIndicatorTag">M {toPrice(bollMid[activeIndex])}</span>
            <span className="chartIndicatorTag">L {toPrice(bollLower[activeIndex])}</span>
          </div>
        </div>
      </div>
      <svg
        className="chartSvg chartSvgInteractive"
        viewBox={`0 0 ${width} ${height}`}
        onPointerMove={handlePointerMove}
        onPointerLeave={() => onHoverChange(null)}
      >
        <rect x="0" y="0" width={width} height={height} fill="rgba(5, 10, 18, 0.88)" />

        {renderYAxis(axisTicks, (value) => y(value), width, (value) => toPrice(value), height)}

        {bars.map((bar, index) => {
          const x = indexToX(index, stepX);
          const openY = y(bar.open);
          const closeValueY = y(bar.close);
          const highY = y(bar.high);
          const lowY = y(bar.low);
          const isBull = bar.close >= bar.open;
          const bodyY = Math.min(openY, closeValueY);
          const bodyHeight = Math.max(1, Math.abs(openY - closeValueY));
          const bodyWidth = Math.max(1, stepX * 0.58);

          return (
            <g key={`${bar.start_at}-${index}`}>
              <line x1={x} x2={x} y1={highY} y2={lowY} stroke={isBull ? "#63d9b4" : "#ff5e7e"} strokeWidth="1" />
              <rect
                x={x - bodyWidth / 2}
                y={bodyY}
                width={bodyWidth}
                height={bodyHeight}
                fill={isBull ? "rgba(99, 217, 180, 0.86)" : "rgba(255, 94, 126, 0.9)"}
              />
            </g>
          );
        })}

        {showBoll ? <path d={upperPath} stroke="#5c8cf7" strokeWidth="1.2" fill="none" opacity="0.9" /> : null}
        {showBoll ? <path d={lowerPath} stroke="#5c8cf7" strokeWidth="1.2" fill="none" opacity="0.9" /> : null}
        {showMa20 ? <path d={ma20Path} stroke="#f9d66b" strokeWidth="1.5" fill="none" /> : null}
        {showMa50 ? <path d={ma50Path} stroke="#ef8ea7" strokeWidth="1.5" fill="none" /> : null}

        <line x1={crossX} x2={crossX} y1={PLOT_TOP_BOTTOM} y2={height - PLOT_TOP_BOTTOM} stroke="rgba(255,255,255,0.28)" strokeDasharray="4 4" />
        <line x1={PLOT_LEFT} x2={width - PLOT_RIGHT} y1={closeY} y2={closeY} stroke="rgba(255,255,255,0.22)" strokeDasharray="4 4" />
        <circle cx={crossX} cy={closeY} r="3.2" fill="rgba(255,255,255,0.95)" />

        <g transform={`translate(${tooltipX}, ${tooltipY})`}>
          <rect width={tooltipWidth} height={tooltipHeight} rx="8" fill="rgba(8,14,24,0.95)" stroke="rgba(116,184,255,0.45)" />
          <text x="10" y="19" fill="#bfd0eb" fontSize="11" fontFamily="JetBrains Mono, monospace">
            {formatDate(activeBar.start_at)}
          </text>
          <text x="10" y="40" fill="#e8edf7" fontSize="12" fontFamily="JetBrains Mono, monospace">
            O {toPrice(activeBar.open)}  H {toPrice(activeBar.high)}
          </text>
          <text x="10" y="58" fill="#e8edf7" fontSize="12" fontFamily="JetBrains Mono, monospace">
            L {toPrice(activeBar.low)}  C {toPrice(activeBar.close)}
          </text>
          <text x="10" y="79" fill="#f9d66b" fontSize="12" fontFamily="JetBrains Mono, monospace">
            MA20 {toPrice(ma20[activeIndex])}  MA50 {toPrice(ma50[activeIndex])}
          </text>
          <text x="10" y="99" fill="#8eb6ff" fontSize="12" fontFamily="JetBrains Mono, monospace">
            BOLL U {toPrice(bollUpper[activeIndex])}
          </text>
          <text x="10" y="117" fill="#8eb6ff" fontSize="12" fontFamily="JetBrains Mono, monospace">
            M {toPrice(bollMid[activeIndex])}  L {toPrice(bollLower[activeIndex])}
          </text>
        </g>
      </svg>
    </section>
  );
}

type MacdPaneProps = {
  line: Array<number | null>;
  signal: Array<number | null>;
  histogram: Array<number | null>;
  labels: string[];
  hoverIndex: number | null;
  onHoverChange: (index: number | null) => void;
};

function MacdPane({ line, signal, histogram, labels, hoverIndex, onHoverChange }: MacdPaneProps) {
  const width = CHART_WIDTH;
  const height = 156;
  const plotWidth = width - PLOT_LEFT - PLOT_RIGHT;
  const stepX = plotWidth / histogram.length;
  const activeIndex = hoverIndex ?? histogram.length - 1;

  const values = [...line, ...signal, ...histogram].filter((value): value is number => value !== null);
  const max = values.length ? Math.max(...values) : 1;
  const min = values.length ? Math.min(...values) : -1;
  const domainMin = Math.min(min, 0);
  const domainMax = Math.max(max, 0);
  const axisTicks = getLinearTicks(domainMin, domainMax, 5);

  const y = (value: number) => scaleValue(value, domainMin, domainMax, height);
  const zeroY = y(0);

  const macdPath = buildLinePath(line, stepX, (value) => y(value), width);
  const signalPath = buildLinePath(signal, stepX, (value) => y(value), width);
  const crossX = indexToX(activeIndex, stepX);
  const activeMacd = line[activeIndex];
  const activeSignal = signal[activeIndex];
  const activeHist = histogram[activeIndex];
  const activeYSource = activeMacd ?? activeSignal ?? activeHist ?? 0;
  const activeY = y(activeYSource);
  const tooltipWidth = 198;
  const tooltipHeight = 82;
  const tooltipX = Math.min(width - tooltipWidth - 10, Math.max(10, crossX + 10));
  const tooltipY = Math.min(height - tooltipHeight - 10, Math.max(10, activeY - tooltipHeight / 2));

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const x = pointerToChartX(event, width);
    onHoverChange(coordinateToIndex(x, stepX, histogram.length));
  }

  return (
    <section className="chartPanel">
      <div className="chartHeader chartHeaderSplit">
        <div className="chartTitleRow">
          <span className="chartTitle">MACD (12,26,9)</span>
          <InfoHint
            title="MACD"
            content="DIF=EMA12-EMA26，DEA=Signal(9)，Hist=DIF-DEA。常用于识别动量变化和趋势拐点。"
          />
        </div>
        <div className="chartIndicatorRow">
          <span className="chartIndicatorTag">MACD {toPrice(line[activeIndex])}</span>
          <span className="chartIndicatorTag">Signal {toPrice(signal[activeIndex])}</span>
          <span className="chartIndicatorTag">Hist {toPrice(histogram[activeIndex])}</span>
        </div>
      </div>
      <svg className="chartSvg chartSvgInteractive" viewBox={`0 0 ${width} ${height}`} onPointerMove={handlePointerMove} onPointerLeave={() => onHoverChange(null)}>
        <rect x="0" y="0" width={width} height={height} fill="rgba(5, 10, 18, 0.86)" />

        {renderYAxis(axisTicks, (value) => y(value), width, (value) => toPrice(value), height)}

        <line x1={PLOT_LEFT} y1={zeroY} x2={width - PLOT_RIGHT} y2={zeroY} stroke="rgba(200, 210, 230, 0.28)" strokeDasharray="3 3" />

        {histogram.map((value, index) => {
          if (value === null) return null;
          const x = PLOT_LEFT + index * stepX + stepX * 0.2;
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

        <line x1={crossX} x2={crossX} y1={PLOT_TOP_BOTTOM} y2={height - PLOT_TOP_BOTTOM} stroke="rgba(255,255,255,0.26)" strokeDasharray="4 4" />

        <g transform={`translate(${tooltipX}, ${tooltipY})`}>
          <rect width={tooltipWidth} height={tooltipHeight} rx="8" fill="rgba(8,14,24,0.95)" stroke="rgba(116,184,255,0.45)" />
          <text x="10" y="20" fill="#bfd0eb" fontSize="11" fontFamily="JetBrains Mono, monospace">
            {formatDate(labels[activeIndex] ?? "")}
          </text>
          <text x="10" y="42" fill="#9ad9ff" fontSize="12" fontFamily="JetBrains Mono, monospace">
            MACD {toPrice(activeMacd)}
          </text>
          <text x="10" y="60" fill="#ffd36a" fontSize="12" fontFamily="JetBrains Mono, monospace">
            Signal {toPrice(activeSignal)}  Hist {toPrice(activeHist)}
          </text>
        </g>
      </svg>
    </section>
  );
}

type RsiPaneProps = {
  values: Array<number | null>;
  labels: string[];
  hoverIndex: number | null;
  onHoverChange: (index: number | null) => void;
};

function RsiPane({ values, labels, hoverIndex, onHoverChange }: RsiPaneProps) {
  const width = CHART_WIDTH;
  const height = 138;
  const plotWidth = width - PLOT_LEFT - PLOT_RIGHT;
  const stepX = plotWidth / values.length;
  const activeIndex = hoverIndex ?? values.length - 1;

  const y = (value: number) => scaleValue(value, 0, 100, height);
  const rsiPath = buildLinePath(values, stepX, (value) => y(value), width);
  const crossX = indexToX(activeIndex, stepX);
  const activeValue = values[activeIndex];
  const activeY = y(activeValue ?? 50);
  const tooltipWidth = 180;
  const tooltipHeight = 68;
  const tooltipX = Math.min(width - tooltipWidth - 10, Math.max(10, crossX + 10));
  const tooltipY = Math.min(height - tooltipHeight - 10, Math.max(10, activeY - tooltipHeight / 2));
  const axisTicks = [0, 30, 50, 70, 100];

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const x = pointerToChartX(event, width);
    onHoverChange(coordinateToIndex(x, stepX, values.length));
  }

  return (
    <section className="chartPanel">
      <div className="chartHeader chartHeaderSplit">
        <div className="chartTitleRow">
          <span className="chartTitle">RSI (14)</span>
          <InfoHint
            title="RSI"
            content="RSI=100-100/(1+RS)，RS=平均涨幅/平均跌幅。常见阈值：70 偏高、30 偏低。"
          />
        </div>
        <div className="chartIndicatorRow">
          <span className="chartIndicatorTag">RSI {toPrice(values[activeIndex])}</span>
        </div>
      </div>
      <svg className="chartSvg chartSvgInteractive" viewBox={`0 0 ${width} ${height}`} onPointerMove={handlePointerMove} onPointerLeave={() => onHoverChange(null)}>
        <rect x="0" y="0" width={width} height={height} fill="rgba(5, 10, 18, 0.86)" />

        {renderYAxis(axisTicks, (value) => y(value), width, (value) => `${Math.round(value)}`, height)}

        <line x1={PLOT_LEFT} y1={y(70)} x2={width - PLOT_RIGHT} y2={y(70)} stroke="rgba(255, 102, 133, 0.45)" strokeDasharray="4 4" />
        <line x1={PLOT_LEFT} y1={y(30)} x2={width - PLOT_RIGHT} y2={y(30)} stroke="rgba(111, 237, 176, 0.45)" strokeDasharray="4 4" />
        <path d={rsiPath} stroke="#84b5ff" strokeWidth="1.5" fill="none" />

        <line x1={crossX} x2={crossX} y1={PLOT_TOP_BOTTOM} y2={height - PLOT_TOP_BOTTOM} stroke="rgba(255,255,255,0.26)" strokeDasharray="4 4" />

        <g transform={`translate(${tooltipX}, ${tooltipY})`}>
          <rect width={tooltipWidth} height={tooltipHeight} rx="8" fill="rgba(8,14,24,0.95)" stroke="rgba(116,184,255,0.45)" />
          <text x="10" y="20" fill="#bfd0eb" fontSize="11" fontFamily="JetBrains Mono, monospace">
            {formatDate(labels[activeIndex] ?? "")}
          </text>
          <text x="10" y="43" fill="#84b5ff" fontSize="12" fontFamily="JetBrains Mono, monospace">
            RSI {toPrice(activeValue)}
          </text>
        </g>
      </svg>
    </section>
  );
}

type VolumePaneProps = {
  bars: MarketBar[];
  volumeMa5: Array<number | null>;
  hoverIndex: number | null;
  onHoverChange: (index: number | null) => void;
  timeTicks: TimeAxisTick[];
};

function VolumePane({ bars, volumeMa5, hoverIndex, onHoverChange, timeTicks }: VolumePaneProps) {
  const width = CHART_WIDTH;
  const height = 136;
  const plotWidth = width - PLOT_LEFT - PLOT_RIGHT;
  const stepX = plotWidth / bars.length;
  const maxVolume = Math.max(...bars.map((bar) => bar.volume), 1);
  const activeIndex = hoverIndex ?? bars.length - 1;
  const activeBar = bars[activeIndex];
  const crossX = indexToX(activeIndex, stepX);
  const activeHeight = Math.max(1, (activeBar.volume / maxVolume) * (height - PLOT_TOP_BOTTOM * 2));
  const activeTopY = height - PLOT_TOP_BOTTOM - activeHeight;
  const tooltipWidth = 198;
  const tooltipHeight = 82;
  const tooltipX = Math.min(width - tooltipWidth - 10, Math.max(10, crossX + 10));
  const tooltipY = Math.min(height - tooltipHeight - 10, Math.max(10, activeTopY - tooltipHeight / 2));

  const axisTicks = getLinearTicks(0, maxVolume, 4);

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const x = pointerToChartX(event, width);
    onHoverChange(coordinateToIndex(x, stepX, bars.length));
  }

  return (
    <section className="chartPanel">
      <div className="chartHeader chartHeaderSplit">
        <div className="chartTitleRow">
          <span className="chartTitle">VOL</span>
          <InfoHint
            title="VOL"
            content="VOL 为成交量，VOL MA5 为 5 周期均量线。量价配合常用于确认趋势强弱。"
          />
        </div>
        <div className="chartIndicatorRow">
          <span className="chartIndicatorTag">{formatDate(activeBar.start_at)}</span>
          <span className="chartIndicatorTag">VOL {formatVolume(activeBar.volume)}</span>
          <span className="chartIndicatorTag">VOL MA5 {formatVolume(volumeMa5[activeIndex])}</span>
        </div>
      </div>
      <svg className="chartSvg chartSvgInteractive" viewBox={`0 0 ${width} ${height}`} onPointerMove={handlePointerMove} onPointerLeave={() => onHoverChange(null)}>
        <rect x="0" y="0" width={width} height={height} fill="rgba(5, 10, 18, 0.86)" />

        {renderYAxis(axisTicks, (value) => scaleValue(value, 0, maxVolume, height), width, (value) => formatVolume(value), height)}

        {timeTicks.map((tick) => {
          const x = indexToX(tick.index, stepX);
          return (
            <line
              key={`vol-grid-${tick.index}`}
              x1={x}
              x2={x}
              y1={PLOT_TOP_BOTTOM}
              y2={height - PLOT_TOP_BOTTOM}
              stroke="rgba(148, 168, 202, 0.13)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
          );
        })}

        {bars.map((bar, index) => {
          const x = PLOT_LEFT + index * stepX + stepX * 0.2;
          const barHeight = Math.max(1, (bar.volume / maxVolume) * (height - PLOT_TOP_BOTTOM * 2));
          const y = height - PLOT_TOP_BOTTOM - barHeight;
          const bullish = bar.close >= bar.open;
          const isActive = index === activeIndex;

          return (
            <rect
              key={`${bar.start_at}-${index}`}
              x={x}
              y={y}
              width={Math.max(1, stepX * 0.6)}
              height={barHeight}
              fill={bullish ? "rgba(99, 217, 180, 0.85)" : "rgba(255, 94, 126, 0.85)"}
              stroke={isActive ? "rgba(240, 245, 255, 0.88)" : "none"}
              strokeWidth={isActive ? 1.1 : 0}
            />
          );
        })}

        <line x1={crossX} x2={crossX} y1={PLOT_TOP_BOTTOM} y2={height - PLOT_TOP_BOTTOM} stroke="rgba(255,255,255,0.26)" strokeDasharray="4 4" />

        <g transform={`translate(${tooltipX}, ${tooltipY})`}>
          <rect width={tooltipWidth} height={tooltipHeight} rx="8" fill="rgba(8,14,24,0.95)" stroke="rgba(116,184,255,0.45)" />
          <text x="10" y="20" fill="#bfd0eb" fontSize="11" fontFamily="JetBrains Mono, monospace">
            {formatDate(activeBar.start_at)}
          </text>
          <text x="10" y="42" fill="#e8edf7" fontSize="12" fontFamily="JetBrains Mono, monospace">
            VOL {formatVolume(activeBar.volume)}
          </text>
          <text x="10" y="60" fill="#a5c7ff" fontSize="12" fontFamily="JetBrains Mono, monospace">
            MA5 {formatVolume(volumeMa5[activeIndex])}
          </text>
        </g>
      </svg>
      <div className="chartXAxis">
        {timeTicks.map((tick) => {
          const isFirst = tick.index === 0;
          const isLast = tick.index === bars.length - 1;
          const alignmentClass = isFirst ? "chartXAxisTickStart" : isLast ? "chartXAxisTickEnd" : "chartXAxisTickMid";

          return (
            <div
              key={`axis-${tick.index}`}
              className={`chartXAxisTick ${alignmentClass}`}
              style={{ left: `${timeTickPercent(tick.index, bars.length)}%` }}
            >
              <span className="chartXAxisMark" />
              <span className="chartXAxisLabel">{tick.label}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

type TimeAxisTick = {
  index: number;
  label: string;
};

function InfoHint({ title, content }: { title: string; content: string }) {
  return (
    <span className="infoHint" aria-label={`${title} indicator explanation`}>
      <span className="infoHintIcon">i</span>
      <span className="infoHintCard">
        <span className="infoHintTitle">{title}</span>
        <span className="infoHintText">{content}</span>
      </span>
    </span>
  );
}

function buildTimeTicks(bars: MarketBar[], maxTicks: number): TimeAxisTick[] {
  if (!bars.length) return [];

  const target = clamp(maxTicks, 2, 10);
  const step = Math.max(1, Math.round((bars.length - 1) / (target - 1)));

  const indexes: number[] = [];
  for (let index = 0; index < bars.length; index += step) {
    indexes.push(index);
  }
  if (indexes[indexes.length - 1] !== bars.length - 1) {
    indexes.push(bars.length - 1);
  }

  return indexes.map((index) => ({
    index,
    label: formatXAxisDate(bars[index]?.start_at ?? "", bars[index]?.timespan ?? bars[0].timespan)
  }));
}

function formatXAxisDate(value: string, timespan: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";

  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  const year = `${date.getFullYear()}`;
  const hour = `${date.getHours()}`.padStart(2, "0");
  const minute = `${date.getMinutes()}`.padStart(2, "0");
  const normalized = timespan.toLowerCase();

  if (normalized === "minute") {
    return `${month}-${day} ${hour}:${minute}`;
  }
  if (normalized === "month") {
    return `${year}-${month}`;
  }
  return `${month}-${day}`;
}

function timeTickPercent(index: number, length: number): number {
  if (length <= 1) return 0;
  return (index / (length - 1)) * 100;
}

function collectPriceRange(
  bars: MarketBar[],
  ma20: Array<number | null>,
  ma50: Array<number | null>,
  bollUpper: Array<number | null>,
  bollLower: Array<number | null>
): { min: number; max: number } {
  const values: number[] = [];
  bars.forEach((bar) => {
    values.push(bar.high, bar.low);
  });
  ma20.forEach((value) => {
    if (value !== null) values.push(value);
  });
  ma50.forEach((value) => {
    if (value !== null) values.push(value);
  });
  bollUpper.forEach((value) => {
    if (value !== null) values.push(value);
  });
  bollLower.forEach((value) => {
    if (value !== null) values.push(value);
  });

  const max = Math.max(...values);
  const min = Math.min(...values);
  const padding = (max - min) * 0.05 || 1;
  return { min: min - padding, max: max + padding };
}

function scaleValue(value: number, min: number, max: number, height: number): number {
  const top = PLOT_TOP_BOTTOM;
  const bottom = height - PLOT_TOP_BOTTOM;
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

    const x = Math.min(width - PLOT_RIGHT, PLOT_LEFT + index * stepX + stepX * 0.5);
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

function coordinateToIndex(x: number, stepX: number, length: number): number {
  const raw = Math.round((x - PLOT_LEFT - stepX * 0.5) / stepX);
  return clamp(raw, 0, length - 1);
}

function indexToX(index: number, stepX: number): number {
  return PLOT_LEFT + index * stepX + stepX * 0.5;
}

function pointerToChartX(event: React.PointerEvent<SVGSVGElement>, width: number): number {
  const rect = event.currentTarget.getBoundingClientRect();
  return ((event.clientX - rect.left) / rect.width) * width;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function toPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toFixed(2);
}

function formatVolume(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  if (value >= 1000000000) return `${(value / 1000000000).toFixed(2)}B`;
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return value.toFixed(0);
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  const hour = `${date.getHours()}`.padStart(2, "0");
  const minute = `${date.getMinutes()}`.padStart(2, "0");
  const hasTime = date.getHours() !== 0 || date.getMinutes() !== 0 || date.getSeconds() !== 0;
  return hasTime ? `${year}-${month}-${day} ${hour}:${minute}` : `${year}-${month}-${day}`;
}

function simpleMovingAverage(values: number[], period: number): Array<number | null> {
  const result: Array<number | null> = new Array(values.length).fill(null);
  let runningSum = 0;

  for (let index = 0; index < values.length; index += 1) {
    runningSum += values[index];
    if (index >= period) {
      runningSum -= values[index - period];
    }
    if (index >= period - 1) {
      result[index] = runningSum / period;
    }
  }

  return result;
}

function getLinearTicks(min: number, max: number, count: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0];
  if (count <= 1) return [min, max];

  const range = max - min;
  if (Math.abs(range) < Number.EPSILON) {
    return [min - 1, min, min + 1];
  }

  const step = range / (count - 1);
  return Array.from({ length: count }).map((_, index) => min + step * index);
}

function renderYAxis(
  ticks: number[],
  toY: (value: number) => number,
  width: number,
  formatter: (value: number) => string,
  height: number
): React.ReactElement {
  return (
    <g>
      {ticks.map((tick, index) => {
        const y = toY(tick);
        const clampedY = Math.max(PLOT_TOP_BOTTOM, Math.min(height - PLOT_TOP_BOTTOM, y));

        return (
          <g key={`${tick}-${index}`}>
            <line
              x1={PLOT_LEFT}
              x2={width - PLOT_RIGHT}
              y1={clampedY}
              y2={clampedY}
              stroke="rgba(148, 168, 202, 0.14)"
              strokeWidth="1"
            />
            <text
              x={width - 6}
              y={clampedY + 4}
              fill="rgba(184, 199, 224, 0.86)"
              fontSize="10"
              textAnchor="end"
              fontFamily="JetBrains Mono, monospace"
            >
              {formatter(tick)}
            </text>
          </g>
        );
      })}
    </g>
  );
}
