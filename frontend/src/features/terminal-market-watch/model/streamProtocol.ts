export type StreamStatusMessage = {
  type: "system.status";
  latency: "real-time" | "delayed" | null;
  connectionState: string | null;
  message: string | null;
};

export type StreamErrorMessage = {
  type: "system.error";
  code: string | null;
  message: string | null;
};

export type StreamPingMessage = {
  type: "system.ping";
};

export type StreamQuoteMessage = {
  type: "market.quote";
  symbol: string;
  eventTs: string;
  bid: number | null;
  ask: number | null;
  bidSize: number | null;
  askSize: number | null;
};

export type StreamTradeMessage = {
  type: "market.trade";
  symbol: string;
  eventTs: string;
  price: number | null;
  last: number | null;
  size: number | null;
};

export type StreamAggregateMessage = {
  type: "market.aggregate";
  symbol: string;
  eventTs: string;
  timespan: string | null;
  multiplier: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  last: number | null;
  volume: number | null;
  vwap: number | null;
};

export type StreamMarketMessage = StreamQuoteMessage | StreamTradeMessage | StreamAggregateMessage;
export type StreamEnvelope = StreamStatusMessage | StreamErrorMessage | StreamPingMessage | StreamMarketMessage;

export function parseStreamEnvelope(raw: string): StreamEnvelope | null {
  const payload = parseJsonObject(raw);
  if (!payload) return null;

  const messageType = asString(payload.type);
  if (!messageType) return null;
  const data = asObject(payload.data) ?? {};
  const defaultTs = asString(payload.ts) ?? new Date().toISOString();

  if (messageType === "system.ping") {
    return { type: "system.ping" };
  }

  if (messageType === "system.status") {
    const latency = asString(data.latency)?.toLowerCase();
    const normalizedLatency = latency === "real-time" || latency === "delayed" ? latency : null;
    return {
      type: "system.status",
      latency: normalizedLatency,
      connectionState: asString(data.connection_state),
      message: asString(data.message)
    };
  }

  if (messageType === "system.error") {
    return {
      type: "system.error",
      code: asString(data.code),
      message: asString(data.message)
    };
  }

  if (messageType === "market.quote") {
    const symbol = normalizeSymbol(asString(data.symbol));
    if (!symbol) return null;
    return {
      type: "market.quote",
      symbol,
      eventTs: asString(data.event_ts) ?? defaultTs,
      bid: asNumber(data.bid),
      ask: asNumber(data.ask),
      bidSize: asNumber(data.bid_size),
      askSize: asNumber(data.ask_size)
    };
  }

  if (messageType === "market.trade") {
    const symbol = normalizeSymbol(asString(data.symbol));
    if (!symbol) return null;
    return {
      type: "market.trade",
      symbol,
      eventTs: asString(data.event_ts) ?? defaultTs,
      price: asNumber(data.price),
      last: asNumber(data.last),
      size: asNumber(data.size)
    };
  }

  if (messageType === "market.aggregate") {
    const symbol = normalizeSymbol(asString(data.symbol));
    if (!symbol) return null;
    return {
      type: "market.aggregate",
      symbol,
      eventTs: asString(data.event_ts) ?? defaultTs,
      timespan: asString(data.timespan),
      multiplier: asNumber(data.multiplier),
      open: asNumber(data.open),
      high: asNumber(data.high),
      low: asNumber(data.low),
      close: asNumber(data.close),
      last: asNumber(data.last),
      volume: asNumber(data.volume),
      vwap: asNumber(data.vwap)
    };
  }

  return null;
}

function parseJsonObject(raw: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      return parsed as Record<string, unknown>;
    }
    return null;
  } catch {
    return null;
  }
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object") {
    return value as Record<string, unknown>;
  }
  return null;
}

function asString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function normalizeSymbol(value: string | null): string {
  return (value ?? "").trim().toUpperCase();
}
