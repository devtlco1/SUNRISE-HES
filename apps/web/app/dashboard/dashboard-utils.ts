/** Reachability buckets from GIS-lite meter_last_seen_at (UTC). */
export type ReachabilityBuckets = {
  online: number;
  offline: number;
  unknown: number;
  sampleSize: number;
};

const DAY_MS = 86_400_000;

export function classifyReachabilityFromLastSeen(
  lastSeenAtIso: string | null | undefined,
  nowMs: number,
  onlineWindowMs: number = DAY_MS,
): "online" | "offline" | "unknown" {
  if (lastSeenAtIso == null || lastSeenAtIso === "") {
    return "unknown";
  }
  const t = Date.parse(lastSeenAtIso);
  if (Number.isNaN(t)) {
    return "unknown";
  }
  if (nowMs - t <= onlineWindowMs) {
    return "online";
  }
  return "offline";
}

export function aggregateReachabilityFromGisEntities(
  items: ReadonlyArray<{ meter_last_seen_at: string | null | undefined }>,
  nowMs: number,
  onlineWindowMs: number = DAY_MS,
): ReachabilityBuckets {
  let online = 0;
  let offline = 0;
  let unknown = 0;
  for (const row of items) {
    const bucket = classifyReachabilityFromLastSeen(row.meter_last_seen_at, nowMs, onlineWindowMs);
    if (bucket === "online") {
      online += 1;
    } else if (bucket === "offline") {
      offline += 1;
    } else {
      unknown += 1;
    }
  }
  return { online, offline, unknown, sampleSize: items.length };
}

const COMMAND_PENDING_LIKE = new Set([
  "pending",
  "scheduled",
  "queued",
  "in_progress",
  "retry_wait",
]);

const COMMAND_FAILED_LIKE = new Set(["failed", "timed_out"]);

export function countCommandStatuses(
  items: ReadonlyArray<{ command_status: string }>,
): { pendingLike: number; failedLike: number } {
  let pendingLike = 0;
  let failedLike = 0;
  for (const row of items) {
    const s = row.command_status;
    if (COMMAND_PENDING_LIKE.has(s)) {
      pendingLike += 1;
    }
    if (COMMAND_FAILED_LIKE.has(s)) {
      failedLike += 1;
    }
  }
  return { pendingLike, failedLike };
}

export function countCommandsSince(
  items: ReadonlyArray<{ created_at: string }>,
  sinceMs: number,
): number {
  let n = 0;
  for (const row of items) {
    const t = Date.parse(row.created_at);
    if (!Number.isNaN(t) && t >= sinceMs) {
      n += 1;
    }
  }
  return n;
}

const JOB_ACTIVE = new Set(["pending", "claimed", "running"]);

export function countActiveJobRuns(items: ReadonlyArray<{ status: string }>): number {
  return items.reduce((acc, row) => acc + (JOB_ACTIVE.has(row.status) ? 1 : 0), 0);
}

export function countFailedJobRuns(items: ReadonlyArray<{ status: string }>): number {
  return items.reduce((acc, row) => acc + (row.status === "failed" ? 1 : 0), 0);
}

export function countEventMatches(
  items: ReadonlyArray<{ severity: string; event_state: string }>,
  severity: string,
  state: string,
): number {
  return items.reduce(
    (acc, row) => acc + (row.severity === severity && row.event_state === state ? 1 : 0),
    0,
  );
}
