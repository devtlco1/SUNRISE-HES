import type { AuthorizedFetch } from "../session-provider";

import {
  aggregateReachabilityFromGisEntities,
  classifyReachabilityFromLastSeen,
  countActiveJobRuns,
  countCommandStatuses,
  countCommandsSince,
  countEventMatches,
  countFailedJobRuns,
} from "./dashboard-utils";

/** Mirrors API list payloads we consume (partial). */
type MeterListHead = { total: number };
type GisLiteList = {
  total: number;
  items: Array<{
    meter_serial_number: string;
    meter_last_seen_at: string | null;
    has_coordinates: boolean;
    service_point_code: string | null;
  }>;
};
type CommandRecentList = {
  total: number;
  limit: number;
  items: Array<{
    command_id: string;
    command_status: string;
    command_template_code: string;
    meter_id: string;
    created_at: string;
    latest_updated_at: string;
  }>;
};
type EventRecentList = {
  total: number;
  items: Array<{
    id: string;
    event_code: string;
    event_name: string | null;
    severity: string;
    event_state: string;
    occurred_at: string;
    meter_id: string | null;
  }>;
};
type JobRunList = {
  total: number;
  items: Array<{
    id: string;
    status: string;
    scheduled_for: string;
    latest_error_message: string | null;
    target_meter_id: string | null;
  }>;
};
type CommunicationEndpointList = { total: number };

export type AttentionRow = {
  id: string;
  kind: "alarm" | "command" | "job" | "reachability";
  label: string;
  detail: string;
  at: string;
};

export type DashboardSnapshot = {
  asOf: string;
  errors: string[];
  metersTotal: number | null;
  reachability: {
    online: number;
    offline: number;
    unknown: number;
    sampleSize: number;
    populationTotal: number | null;
  } | null;
  commands24h: number | null;
  commandsRecentLimit: number | null;
  commandsPendingLike: number | null;
  commandsFailedLike: number | null;
  approvalsPendingTotal: number | null;
  criticalOpenInWindow: number | null;
  warningOpenInWindow: number | null;
  eventsWindowLimit: number | null;
  eventsIngestedTotal: number | null;
  activeJobRunsInWindow: number | null;
  failedJobRunsInWindow: number | null;
  jobRunsWindowLimit: number | null;
  communicationEndpoints: number | null;
  readingActivityAvailable: boolean;
  gisMappedInSample: number | null;
  gisUnmappedInSample: number | null;
  servicePointsWithOfflineInSample: number | null;
  attention: AttentionRow[];
};

function pushError(errors: string[], label: string, err: unknown) {
  const msg = err instanceof Error ? err.message : String(err);
  errors.push(`${label}: ${msg}`);
}

export async function fetchDashboardSnapshot(
  authorizedFetch: AuthorizedFetch,
): Promise<DashboardSnapshot> {
  const asOf = new Date().toISOString();
  const nowMs = Date.parse(asOf);
  const since24h = nowMs - 86_400_000;
  const errors: string[] = [];

  const settled = await Promise.allSettled([
    authorizedFetch<MeterListHead>("/api/v1/meters?limit=1"),
    authorizedFetch<GisLiteList>("/api/v1/gis-lite/entities?limit=200"),
    authorizedFetch<CommandRecentList>("/api/v1/commands/recent?limit=100"),
    authorizedFetch<CommandRecentList>("/api/v1/commands/approvals/pending?limit=50"),
    authorizedFetch<EventRecentList>("/api/v1/events/recent?limit=500"),
    authorizedFetch<JobRunList>("/api/v1/job-runs?limit=100"),
    authorizedFetch<CommunicationEndpointList>("/api/v1/communication-endpoints"),
  ]);

  let metersTotal: number | null = null;
  if (settled[0].status === "fulfilled") {
    metersTotal = settled[0].value.total;
  } else {
    pushError(errors, "Meters", settled[0].reason);
  }

  let reachability: DashboardSnapshot["reachability"] = null;
  let gisMappedInSample: number | null = null;
  let gisUnmappedInSample: number | null = null;
  let servicePointsWithOfflineInSample: number | null = null;
  if (settled[1].status === "fulfilled") {
    const gis = settled[1].value;
    const buckets = aggregateReachabilityFromGisEntities(gis.items, nowMs);
    reachability = {
      ...buckets,
      populationTotal: gis.total,
    };
    gisMappedInSample = gis.items.filter((r) => r.has_coordinates).length;
    gisUnmappedInSample = gis.items.length - gisMappedInSample;
    const offlineSp = new Set<string>();
    for (const row of gis.items) {
      if (
        row.service_point_code &&
        classifyReachabilityFromLastSeen(row.meter_last_seen_at, nowMs) === "offline"
      ) {
        offlineSp.add(row.service_point_code);
      }
    }
    servicePointsWithOfflineInSample = offlineSp.size;
  } else {
    pushError(errors, "GIS snapshot", settled[1].reason);
  }

  let commands24h: number | null = null;
  let commandsPendingLike: number | null = null;
  let commandsFailedLike: number | null = null;
  let commandsRecentLimit: number | null = null;
  if (settled[2].status === "fulfilled") {
    const cmd = settled[2].value;
    commandsRecentLimit = cmd.limit;
    commands24h = countCommandsSince(cmd.items, since24h);
    const st = countCommandStatuses(cmd.items);
    commandsPendingLike = st.pendingLike;
    commandsFailedLike = st.failedLike;
  } else {
    pushError(errors, "Commands", settled[2].reason);
  }

  let approvalsPendingTotal: number | null = null;
  if (settled[3].status === "fulfilled") {
    approvalsPendingTotal = settled[3].value.total;
  } else {
    pushError(errors, "Command approvals", settled[3].reason);
  }

  let criticalOpenInWindow: number | null = null;
  let warningOpenInWindow: number | null = null;
  let eventsWindowLimit: number | null = null;
  let eventsIngestedTotal: number | null = null;
  const eventItems: EventRecentList["items"] =
    settled[4].status === "fulfilled" ? settled[4].value.items : [];
  if (settled[4].status === "fulfilled") {
    const ev = settled[4].value;
    eventsWindowLimit = ev.items.length;
    eventsIngestedTotal = ev.total;
    criticalOpenInWindow = countEventMatches(ev.items, "critical", "open");
    warningOpenInWindow = countEventMatches(ev.items, "warning", "open");
  } else {
    pushError(errors, "Events", settled[4].reason);
  }

  let activeJobRunsInWindow: number | null = null;
  let failedJobRunsInWindow: number | null = null;
  let jobRunsWindowLimit: number | null = null;
  const jobItems: JobRunList["items"] =
    settled[5].status === "fulfilled" ? settled[5].value.items : [];
  if (settled[5].status === "fulfilled") {
    const jobs = settled[5].value;
    jobRunsWindowLimit = jobs.items.length;
    activeJobRunsInWindow = countActiveJobRuns(jobs.items);
    failedJobRunsInWindow = countFailedJobRuns(jobs.items);
  } else {
    pushError(errors, "Job runs", settled[5].reason);
  }

  let communicationEndpoints: number | null = null;
  if (settled[6].status === "fulfilled") {
    communicationEndpoints = settled[6].value.total;
  } else {
    pushError(errors, "Communication endpoints", settled[6].reason);
  }

  const attention = buildAttentionQueue({
    asOfIso: asOf,
    eventItems,
    commandItems: settled[2].status === "fulfilled" ? settled[2].value.items : [],
    jobItems,
    gisItems: settled[1].status === "fulfilled" ? settled[1].value.items : [],
    nowMs,
  });

  return {
    asOf,
    errors,
    metersTotal,
    reachability,
    commands24h,
    commandsRecentLimit,
    commandsPendingLike,
    commandsFailedLike,
    approvalsPendingTotal,
    criticalOpenInWindow,
    warningOpenInWindow,
    eventsWindowLimit,
    eventsIngestedTotal,
    activeJobRunsInWindow,
    failedJobRunsInWindow,
    jobRunsWindowLimit,
    communicationEndpoints,
    readingActivityAvailable: false,
    gisMappedInSample,
    gisUnmappedInSample,
    servicePointsWithOfflineInSample,
    attention,
  };
}

function buildAttentionQueue(input: {
  asOfIso: string;
  eventItems: EventRecentList["items"];
  commandItems: CommandRecentList["items"];
  jobItems: JobRunList["items"];
  gisItems: GisLiteList["items"];
  nowMs: number;
}): AttentionRow[] {
  const rows: AttentionRow[] = [];

  for (const ev of input.eventItems) {
    if (ev.severity === "critical" && ev.event_state === "open") {
      rows.push({
        id: `alarm-${ev.id}`,
        kind: "alarm",
        label: "Critical alarm · open",
        detail: `${ev.event_code}${ev.event_name ? ` — ${ev.event_name}` : ""}`,
        at: ev.occurred_at,
      });
    }
  }

  for (const cmd of input.commandItems) {
    if (cmd.command_status === "failed" || cmd.command_status === "timed_out") {
      rows.push({
        id: `cmd-${cmd.command_id}`,
        kind: "command",
        label: `Command ${cmd.command_status.replace(/_/g, " ")}`,
        detail: `${cmd.command_template_code} · meter ${cmd.meter_id.slice(0, 8)}…`,
        at: cmd.latest_updated_at,
      });
    }
  }

  for (const job of input.jobItems) {
    if (job.status === "failed") {
      rows.push({
        id: `job-${job.id}`,
        kind: "job",
        label: "Job run failed",
        detail: job.latest_error_message ?? "No error message recorded.",
        at: job.scheduled_for,
      });
    }
  }

  let reachAdds = 0;
  for (const g of input.gisItems) {
    if (reachAdds >= 3) {
      break;
    }
    if (classifyReachabilityFromLastSeen(g.meter_last_seen_at, input.nowMs) === "unknown") {
      rows.push({
        id: `reach-${g.meter_serial_number}`,
        kind: "reachability",
        label: "No last-seen timestamp (GIS sample)",
        detail: `Serial ${g.meter_serial_number}`,
        at: input.asOfIso,
      });
      reachAdds += 1;
    }
  }

  rows.sort((a, b) => Date.parse(b.at) - Date.parse(a.at));

  const seen = new Set<string>();
  const deduped: AttentionRow[] = [];
  for (const r of rows) {
    if (seen.has(r.id)) {
      continue;
    }
    seen.add(r.id);
    deduped.push(r);
    if (deduped.length >= 10) {
      break;
    }
  }
  return deduped;
}
