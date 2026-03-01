import { describe, expect, it } from "vitest";

import { formatReplayTime } from "./presentation";

describe("formatReplayTime", () => {
  it("formats replay timestamps in America/New_York time", () => {
    expect(formatReplayTime("2026-02-26T15:05:00Z")).toBe("10:05:00");
  });

  it("returns fallback for invalid input", () => {
    expect(formatReplayTime("not-a-date")).toBe("-");
    expect(formatReplayTime(null)).toBe("-");
  });
});
