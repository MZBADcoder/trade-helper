import { type MarketBar } from "./types";

export type IndicatorBundle = {
  ma20: Array<number | null>;
  ma50: Array<number | null>;
  macdLine: Array<number | null>;
  macdSignal: Array<number | null>;
  macdHistogram: Array<number | null>;
  bollMid: Array<number | null>;
  bollUpper: Array<number | null>;
  bollLower: Array<number | null>;
  rsi14: Array<number | null>;
};

export function buildIndicators(bars: MarketBar[]): IndicatorBundle {
  const closes = bars.map((bar) => bar.close);

  const ma20 = simpleMovingAverage(closes, 20);
  const ma50 = simpleMovingAverage(closes, 50);

  const ema12 = exponentialMovingAverage(closes, 12);
  const ema26 = exponentialMovingAverage(closes, 26);
  const macdLine = closes.map((_, index) =>
    ema12[index] !== null && ema26[index] !== null ? (ema12[index] as number) - (ema26[index] as number) : null
  );
  const macdSignal = exponentialMovingAverageFromSeries(macdLine, 9);
  const macdHistogram = macdLine.map((value, index) =>
    value !== null && macdSignal[index] !== null ? value - (macdSignal[index] as number) : null
  );

  const boll = bollingerBands(closes, 20, 2);
  const rsi14 = relativeStrengthIndex(closes, 14);

  return {
    ma20,
    ma50,
    macdLine,
    macdSignal,
    macdHistogram,
    bollMid: boll.mid,
    bollUpper: boll.upper,
    bollLower: boll.lower,
    rsi14
  };
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

function exponentialMovingAverage(values: number[], period: number): Array<number | null> {
  const result: Array<number | null> = new Array(values.length).fill(null);
  if (values.length < period) return result;

  let seed = 0;
  for (let index = 0; index < period; index += 1) {
    seed += values[index];
  }

  let prevEma = seed / period;
  result[period - 1] = prevEma;

  const alpha = 2 / (period + 1);
  for (let index = period; index < values.length; index += 1) {
    prevEma = values[index] * alpha + prevEma * (1 - alpha);
    result[index] = prevEma;
  }

  return result;
}

function exponentialMovingAverageFromSeries(
  values: Array<number | null>,
  period: number
): Array<number | null> {
  const result: Array<number | null> = new Array(values.length).fill(null);
  const firstValid = values.findIndex((value) => value !== null);
  if (firstValid < 0) return result;

  const validWindow: number[] = [];
  for (let index = firstValid; index < values.length; index += 1) {
    const value = values[index];
    if (value === null) continue;
    validWindow.push(value);
    if (validWindow.length === period) {
      let prevEma = validWindow.reduce((sum, current) => sum + current, 0) / period;
      const seedIndex = index;
      result[seedIndex] = prevEma;

      const alpha = 2 / (period + 1);
      for (let nextIndex = seedIndex + 1; nextIndex < values.length; nextIndex += 1) {
        const nextValue = values[nextIndex];
        if (nextValue === null) continue;
        prevEma = nextValue * alpha + prevEma * (1 - alpha);
        result[nextIndex] = prevEma;
      }
      break;
    }
  }

  return result;
}

function bollingerBands(values: number[], period: number, sigmaMultiplier: number): {
  mid: Array<number | null>;
  upper: Array<number | null>;
  lower: Array<number | null>;
} {
  const mid = simpleMovingAverage(values, period);
  const upper: Array<number | null> = new Array(values.length).fill(null);
  const lower: Array<number | null> = new Array(values.length).fill(null);

  for (let index = period - 1; index < values.length; index += 1) {
    const mean = mid[index];
    if (mean === null) continue;

    let variance = 0;
    for (let inner = index - period + 1; inner <= index; inner += 1) {
      const delta = values[inner] - mean;
      variance += delta * delta;
    }

    const deviation = Math.sqrt(variance / period);
    upper[index] = mean + sigmaMultiplier * deviation;
    lower[index] = mean - sigmaMultiplier * deviation;
  }

  return { mid, upper, lower };
}

function relativeStrengthIndex(values: number[], period: number): Array<number | null> {
  const result: Array<number | null> = new Array(values.length).fill(null);
  if (values.length <= period) return result;

  let gains = 0;
  let losses = 0;

  for (let index = 1; index <= period; index += 1) {
    const delta = values[index] - values[index - 1];
    if (delta >= 0) gains += delta;
    else losses += Math.abs(delta);
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;
  result[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);

  for (let index = period + 1; index < values.length; index += 1) {
    const delta = values[index] - values[index - 1];
    const gain = delta > 0 ? delta : 0;
    const loss = delta < 0 ? Math.abs(delta) : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    result[index] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }

  return result;
}
