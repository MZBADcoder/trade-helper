const MARKET_TIME_ZONE = "America/New_York";
const REPLAY_TIME_FORMATTER = new Intl.DateTimeFormat("en-US", {
  timeZone: MARKET_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false
});

export function toPrice(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "-";
  return `$${value.toFixed(2)}`;
}

export function toSigned(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "-";
  if (value === 0) return "0.00";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

export function toSignedPercent(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "-";
  if (value === 0) return "0.00%";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function toVolume(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "-";
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return value.toFixed(0);
}

export function formatReplayTime(value: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "-";
  return REPLAY_TIME_FORMATTER.format(parsed);
}
