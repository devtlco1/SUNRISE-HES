import { describe, expect, it } from "vitest";

import {
  aggregateReachabilityFromGisEntities,
  classifyReachabilityFromLastSeen,
  countActiveJobRuns,
  countCommandStatuses,
  countCommandsSince,
  countEventMatches,
  countFailedJobRuns,
} from "./dashboard-utils";

describe("classifyReachabilityFromLastSeen", () => {
  const now = Date.parse("2026-04-05T12:00:00.000Z");

  it("returns unknown for null or empty", () => {
    expect(classifyReachabilityFromLastSeen(null, now)).toBe("unknown");
    expect(classifyReachabilityFromLastSeen("", now)).toBe("unknown");
  });

  it("returns online within default 24h window", () => {
    expect(classifyReachabilityFromLastSeen("2026-04-05T10:00:00.000Z", now)).toBe("online");
  });

  it("returns offline when older than window", () => {
    expect(classifyReachabilityFromLastSeen("2026-04-03T10:00:00.000Z", now)).toBe("offline");
  });
});

describe("aggregateReachabilityFromGisEntities", () => {
  const now = Date.parse("2026-04-05T12:00:00.000Z");

  it("aggregates buckets", () => {
    const r = aggregateReachabilityFromGisEntities(
      [
        { meter_last_seen_at: "2026-04-05T11:00:00.000Z" },
        { meter_last_seen_at: "2026-04-01T10:00:00.000Z" },
        { meter_last_seen_at: null },
      ],
      now,
    );
    expect(r).toEqual({ online: 1, offline: 1, unknown: 1, sampleSize: 3 });
  });
});

describe("countCommandStatuses", () => {
  it("counts pending-like and failed-like", () => {
    const r = countCommandStatuses([
      { command_status: "pending" },
      { command_status: "failed" },
      { command_status: "succeeded" },
    ]);
    expect(r).toEqual({ pendingLike: 1, failedLike: 1 });
  });
});

describe("countCommandsSince", () => {
  it("counts by created_at", () => {
    const since = Date.parse("2026-04-04T00:00:00.000Z");
    const n = countCommandsSince(
      [{ created_at: "2026-04-05T01:00:00.000Z" }, { created_at: "2026-04-03T01:00:00.000Z" }],
      since,
    );
    expect(n).toBe(1);
  });
});

describe("job run helpers", () => {
  it("countActiveJobRuns", () => {
    expect(
      countActiveJobRuns([{ status: "pending" }, { status: "succeeded" }, { status: "running" }]),
    ).toBe(2);
  });

  it("countFailedJobRuns", () => {
    expect(countFailedJobRuns([{ status: "failed" }, { status: "pending" }])).toBe(1);
  });
});

describe("countEventMatches", () => {
  it("filters severity and state", () => {
    expect(
      countEventMatches(
        [
          { severity: "critical", event_state: "open" },
          { severity: "critical", event_state: "resolved" },
          { severity: "warning", event_state: "open" },
        ],
        "critical",
        "open",
      ),
    ).toBe(1);
  });
});
