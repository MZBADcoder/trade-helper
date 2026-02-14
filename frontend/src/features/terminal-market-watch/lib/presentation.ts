import { type StreamStatus } from "../model/types";

export function toPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `$${value.toFixed(2)}`;
}

export function toSigned(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  if (value > 0) return `+${value.toFixed(2)}`;
  return value.toFixed(2);
}

export function toSignedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  if (value > 0) return `+${value.toFixed(2)}%`;
  return `${value.toFixed(2)}%`;
}

export function toVolume(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(0);
}

export function formatTime(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleTimeString();
}

export function formatDateTime(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

export function snapshotToneClass(value: number): string {
  if (value > 0) return "toneUp";
  if (value < 0) return "toneDown";
  return "toneFlat";
}

export function streamStatusLabel(status: StreamStatus): string {
  switch (status) {
    case "connecting":
      return "Connecting";
    case "connected":
      return "Connected";
    case "reconnecting":
      return "Reconnecting";
    case "degraded":
      return "Degraded";
    case "disconnected":
      return "Disconnected";
    case "idle":
    default:
      return "Idle";
  }
}

export function streamStatusClass(status: StreamStatus): string {
  switch (status) {
    case "connected":
      return "statusConnected";
    case "reconnecting":
    case "connecting":
      return "statusReconnecting";
    case "degraded":
      return "statusDegraded";
    case "disconnected":
      return "statusDisconnected";
    case "idle":
    default:
      return "statusIdle";
  }
}

export function shrinkText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 3)}...`;
}
