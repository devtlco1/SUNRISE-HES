"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type MeterItem = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  manufacturer_code: string;
  meter_model_code: string;
  communication_profile_code: string | null;
  meter_profile_code: string | null;
  current_status: string;
  last_seen_at: string | null;
  is_active: boolean;
};

type MeterListResponse = {
  total: number;
  items: MeterItem[];
};

type MeterEndpointAssignment = {
  id: string;
  endpoint_code: string;
  endpoint_display_name: string;
  assignment_status: string;
  is_primary: boolean;
};

type MeterEndpointAssignmentListResponse = {
  total: number;
  items: MeterEndpointAssignment[];
};

type ConnectivitySession = {
  id: string;
  started_at: string;
  ended_at: string | null;
  status: string;
  session_purpose: string;
};

type ConnectivitySessionHistoryListResponse = {
  total: number;
  items: ConnectivitySession[];
};

type ConnectivityOverviewRow = {
  meter: MeterItem;
  primaryEndpoint: MeterEndpointAssignment | null;
  latestSession: ConnectivitySession | null;
};

type StatusTone = "positive" | "warning" | "danger" | "neutral";
type ConnectivityIncidentState = "offline" | "stale" | "degraded";
type ConnectivityIncidentSeverity = "critical" | "warning";

type FreshnessContext = {
  label: string;
  tone: StatusTone;
  sortWeight: number;
};

type ConnectivityIncident = {
  state: ConnectivityIncidentState;
  severity: ConnectivityIncidentSeverity;
  summary: string;
  sortWeight: number;
};

type ConnectivityIncidentFilter = "all" | ConnectivityIncidentState;

type ConnectivityIncidentRow = {
  row: ConnectivityOverviewRow;
  freshnessContext: FreshnessContext;
  incident: ConnectivityIncident;
};

const STALE_SIGNAL_THRESHOLD_MS = 1000 * 60 * 60 * 24;

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatFreshnessHint(lastSeenAt: string | null): string {
  return lastSeenAt ? "Recent signal recorded" : "No recent signal";
}

function formatDurationFromMs(durationMs: number): string {
  const clampedDurationMs = Math.max(durationMs, 0);
  const totalMinutes = Math.floor(clampedDurationMs / (1000 * 60));
  if (totalMinutes < 60) {
    return totalMinutes <= 1 ? "1 minute" : `${totalMinutes} minutes`;
  }

  const totalHours = Math.floor(totalMinutes / 60);
  if (totalHours < 24) {
    return totalHours === 1 ? "1 hour" : `${totalHours} hours`;
  }

  const totalDays = Math.floor(totalHours / 24);
  return totalDays === 1 ? "1 day" : `${totalDays} days`;
}

function formatLatestSessionSummary(session: ConnectivitySession | null): string {
  if (!session) {
    return "No recent session";
  }
  return `${session.status} (${session.session_purpose})`;
}

function isLiveSession(session: ConnectivitySession | null): boolean {
  return session?.status === "started" && session.ended_at === null;
}

function buildSessionHealthLabel(
  session: ConnectivitySession | null,
  freshnessContext: FreshnessContext | null,
): string {
  if (!session) {
    return "No live session";
  }
  if (freshnessContext?.tone === "danger") {
    return "Live session with no recent signal";
  }
  if (freshnessContext?.tone === "warning") {
    return "Live session needs freshness review";
  }
  return "Live session healthy";
}

function buildSessionHealthTone(freshnessContext: FreshnessContext | null): StatusTone {
  return freshnessContext?.tone ?? "neutral";
}

function formatStatusLabel(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildStatusTone(value: string | null): StatusTone {
  const normalized = value?.toLowerCase() ?? "";
  if (
    normalized.includes("succeed") ||
    normalized.includes("active") ||
    normalized.includes("commissioned") ||
    normalized.includes("healthy")
  ) {
    return "positive";
  }
  if (
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized.includes("inactive") ||
    normalized.includes("offline")
  ) {
    return "danger";
  }
  if (
    normalized.includes("pending") ||
    normalized.includes("register") ||
    normalized.includes("queued") ||
    normalized.includes("stale") ||
    normalized.includes("degraded")
  ) {
    return "warning";
  }
  return "neutral";
}

function buildSeverityTone(value: ConnectivityIncidentSeverity): StatusTone {
  return value === "critical" ? "danger" : "warning";
}

function getFreshnessContext(lastSeenAt: string | null): FreshnessContext {
  if (!lastSeenAt) {
    return {
      label: "No recent signal",
      tone: "danger",
      sortWeight: 0,
    };
  }

  const lastSeenDate = new Date(lastSeenAt);
  if (Number.isNaN(lastSeenDate.getTime())) {
    return {
      label: "Signal freshness unavailable",
      tone: "neutral",
      sortWeight: 3,
    };
  }

  const ageMs = Date.now() - lastSeenDate.getTime();
  if (ageMs >= STALE_SIGNAL_THRESHOLD_MS) {
    return {
      label: `Signal stale for ${formatDurationFromMs(ageMs)}`,
      tone: "warning",
      sortWeight: 1,
    };
  }

  return {
    label: `Recent signal ${formatDurationFromMs(ageMs)} ago`,
    tone: "positive",
    sortWeight: 2,
  };
}

function buildConnectivityIncident(
  row: ConnectivityOverviewRow,
  freshnessContext: FreshnessContext,
): ConnectivityIncident | null {
  if (row.meter.last_seen_at === null) {
    return {
      state: "offline",
      severity: "critical",
      summary: row.latestSession
        ? `Latest session ${formatStatusLabel(row.latestSession.status)} with no recent signal recorded.`
        : "No recent signal or connectivity session is currently recorded.",
      sortWeight: 0,
    };
  }

  const latestSessionStatus = row.latestSession?.status.toLowerCase() ?? "";
  if (
    latestSessionStatus === "failed" ||
    latestSessionStatus === "timed_out" ||
    latestSessionStatus === "cancelled"
  ) {
    return {
      state: "degraded",
      severity: "warning",
      summary: `Latest session ${formatStatusLabel(row.latestSession?.status ?? "failed")} requires operator review.`,
      sortWeight: 1,
    };
  }

  if (freshnessContext.sortWeight === 1) {
    return {
      state: "stale",
      severity: "warning",
      summary: "Last signal is older than the current bounded operational freshness window.",
      sortWeight: 2,
    };
  }

  return null;
}

function buildIncidentPostureLabel(
  row: ConnectivityOverviewRow,
  freshnessContext: FreshnessContext,
  incident: ConnectivityIncident,
): string {
  if (incident.state === "offline") {
    return row.primaryEndpoint
      ? "Meter is offline even though an endpoint assignment is present."
      : "Meter is offline and has no active endpoint assignment in view.";
  }
  if (incident.state === "stale") {
    return row.primaryEndpoint
      ? "Signal freshness drift is visible on the currently assigned endpoint."
      : "Signal freshness drift is visible without endpoint context.";
  }
  if (row.latestSession) {
    return `Latest ${formatStatusLabel(row.latestSession.session_purpose).toLowerCase()} session ${formatStatusLabel(row.latestSession.status).toLowerCase()} and needs review.`;
  }
  return `${freshnessContext.label} and no recent session detail is available in the bounded view.`;
}

function buildDisconnectCue(session: ConnectivitySession | null): string {
  if (!session) {
    return "No recent disconnect cue in view";
  }
  if (
    session.status === "failed" ||
    session.status === "timed_out" ||
    session.status === "cancelled"
  ) {
    return `Latest disconnect cue ${formatStatusLabel(session.status)}`;
  }
  if (session.status === "started") {
    return "Session remains active";
  }
  return "No recent disconnect cue in view";
}

function buildLatestSessionBucketLabel(session: ConnectivitySession | null): string {
  if (!session) {
    return "No recent session";
  }
  if (session.status === "failed" || session.status === "timed_out" || session.status === "cancelled") {
    return "Failed / timed out / cancelled";
  }
  return formatStatusLabel(session.status);
}

export function ConnectivityModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [rows, setRows] = useState<ConnectivityOverviewRow[]>([]);
  const [selectedMeterId, setSelectedMeterId] = useState<string | null>(null);
  const [incidentFilter, setIncidentFilter] = useState<ConnectivityIncidentFilter>("all");
  const [totalMeters, setTotalMeters] = useState(0);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingOverview, setIsLoadingOverview] = useState(false);

  const loadConnectivityOverview = useCallback(async () => {
    setIsLoadingOverview(true);
    setPageError(null);

    try {
      const metersResponse = await authorizedFetch<MeterListResponse>(
        "/api/v1/meters?offset=0&limit=20",
      );

      const rowResults = await Promise.all(
        metersResponse.items.map(async (meter) => {
          const [assignmentsResult, sessionsResult] = await Promise.allSettled([
            authorizedFetch<MeterEndpointAssignmentListResponse>(
              `/api/v1/meters/${meter.id}/endpoint-assignments`,
            ),
            authorizedFetch<ConnectivitySessionHistoryListResponse>(
              `/api/v1/meters/${meter.id}/sessions?limit=1`,
            ),
          ]);

          const primaryEndpoint =
            assignmentsResult.status === "fulfilled"
              ? assignmentsResult.value.items.find((item) => item.is_primary) ??
                assignmentsResult.value.items.find(
                  (item) => item.assignment_status === "active",
                ) ??
                null
              : null;

          const latestSession =
            sessionsResult.status === "fulfilled"
              ? sessionsResult.value.items[0] ?? null
              : null;

          return {
            meter,
            primaryEndpoint,
            latestSession,
            contextUnavailable:
              assignmentsResult.status === "rejected" ||
              sessionsResult.status === "rejected",
          };
        }),
      );

      const nextRows = rowResults.map(({ meter, primaryEndpoint, latestSession }) => ({
        meter,
        primaryEndpoint,
        latestSession,
      }));
      setRows(nextRows);
      setSelectedMeterId((currentSelectedMeterId) => {
        if (currentSelectedMeterId && nextRows.some((row) => row.meter.id === currentSelectedMeterId)) {
          return currentSelectedMeterId;
        }
        return nextRows[0]?.meter.id ?? null;
      });
      setTotalMeters(metersResponse.total);

      if (rowResults.some((item) => item.contextUnavailable)) {
        setPageError("Unable to load complete connectivity overview context.");
      }
    } catch (error) {
      setRows([]);
      setSelectedMeterId(null);
      setTotalMeters(0);
      setPageError(
        error instanceof Error
          ? error.message
          : "Unable to load connectivity overview.",
      );
    } finally {
      setIsLoadingOverview(false);
    }
  }, [authorizedFetch]);

  useEffect(() => {
    void loadConnectivityOverview();
  }, [loadConnectivityOverview]);

  const overviewStats = useMemo(() => {
    const metersWithEndpoint = rows.filter((row) => row.primaryEndpoint !== null).length;
    const metersWithSignal = rows.filter((row) => row.meter.last_seen_at !== null).length;
    const latestSucceeded = rows.filter(
      (row) => row.latestSession?.status === "succeeded",
    ).length;
    const incidentCount = rows.filter((row) => {
      const freshnessContext = getFreshnessContext(row.meter.last_seen_at);
      return buildConnectivityIncident(row, freshnessContext) !== null;
    }).length;

    return {
      metersWithEndpoint,
      metersWithSignal,
      latestSucceeded,
      incidentCount,
    };
  }, [rows]);

  const incidentRows = useMemo(
    () =>
      rows
        .map((row) => {
          const freshnessContext = getFreshnessContext(row.meter.last_seen_at);
          const incident = buildConnectivityIncident(row, freshnessContext);
          return {
            row,
            freshnessContext,
            incident,
          };
        })
        .filter(
          (
            item,
          ): item is ConnectivityIncidentRow => item.incident !== null,
        )
        .sort((left, right) => {
          if (left.incident.sortWeight !== right.incident.sortWeight) {
            return left.incident.sortWeight - right.incident.sortWeight;
          }

          if (left.freshnessContext.sortWeight !== right.freshnessContext.sortWeight) {
            return left.freshnessContext.sortWeight - right.freshnessContext.sortWeight;
          }

          return left.row.meter.serial_number.localeCompare(right.row.meter.serial_number);
        }),
    [rows],
  );
  const filteredIncidentRows = useMemo(
    () =>
      incidentRows.filter((item) =>
        incidentFilter === "all" ? true : item.incident.state === incidentFilter,
      ),
    [incidentFilter, incidentRows],
  );
  const incidentStats = useMemo(() => {
    const rowsInScope = filteredIncidentRows;
    return {
      visible: rowsInScope.length,
      offline: rowsInScope.filter((item) => item.incident.state === "offline").length,
      stale: rowsInScope.filter((item) => item.incident.state === "stale").length,
      degraded: rowsInScope.filter((item) => item.incident.state === "degraded").length,
      withoutEndpoint: rowsInScope.filter((item) => item.row.primaryEndpoint === null).length,
      disconnectCues: rowsInScope.filter((item) => {
        const latestStatus = item.row.latestSession?.status;
        return (
          latestStatus === "failed" ||
          latestStatus === "timed_out" ||
          latestStatus === "cancelled"
        );
      }).length,
    };
  }, [filteredIncidentRows]);
  const selectedIncidentRow = useMemo(
    () =>
      filteredIncidentRows.find((item) => item.row.meter.id === selectedMeterId) ??
      filteredIncidentRows[0] ??
      null,
    [filteredIncidentRows, selectedMeterId],
  );

  const selectedRow = useMemo(
    () => rows.find((row) => row.meter.id === selectedMeterId) ?? rows[0] ?? null,
    [rows, selectedMeterId],
  );
  const selectedRowFreshnessContext = useMemo(
    () => (selectedRow ? getFreshnessContext(selectedRow.meter.last_seen_at) : null),
    [selectedRow],
  );
  const selectedRowIncident = useMemo(
    () =>
      selectedRow && selectedRowFreshnessContext
        ? buildConnectivityIncident(selectedRow, selectedRowFreshnessContext)
        : null,
    [selectedRow, selectedRowFreshnessContext],
  );
  const liveSessionRows = useMemo(
    () =>
      rows
        .filter((row) => isLiveSession(row.latestSession))
        .sort((left, right) => {
          const leftStartedAt = new Date(left.latestSession?.started_at ?? 0).getTime();
          const rightStartedAt = new Date(right.latestSession?.started_at ?? 0).getTime();
          return rightStartedAt - leftStartedAt;
        }),
    [rows],
  );
  const liveSessionStats = useMemo(() => {
    const withRecentSignal = liveSessionRows.filter((row) => {
      const freshness = getFreshnessContext(row.meter.last_seen_at);
      return freshness.tone === "positive";
    }).length;
    const withEndpoint = liveSessionRows.filter((row) => row.primaryEndpoint !== null).length;
    return {
      total: liveSessionRows.length,
      withRecentSignal,
      withEndpoint,
    };
  }, [liveSessionRows]);
  const reportStats = useMemo(() => {
    const healthyRecentSignal = rows.filter((row) => {
      const freshnessContext = getFreshnessContext(row.meter.last_seen_at);
      return (
        freshnessContext.tone === "positive" &&
        buildConnectivityIncident(row, freshnessContext) === null
      );
    }).length;
    const missingEndpoint = rows.filter((row) => row.primaryEndpoint === null).length;
    const noRecentSession = rows.filter((row) => row.latestSession === null).length;
    const disconnectCues = rows.filter((row) => {
      const latestStatus = row.latestSession?.status;
      return (
        latestStatus === "failed" ||
        latestStatus === "timed_out" ||
        latestStatus === "cancelled"
      );
    }).length;
    return {
      healthyRecentSignal,
      offline: incidentRows.filter((item) => item.incident.state === "offline").length,
      stale: incidentRows.filter((item) => item.incident.state === "stale").length,
      degraded: incidentRows.filter((item) => item.incident.state === "degraded").length,
      disconnectCues,
      missingEndpoint,
      noRecentSession,
    };
  }, [incidentRows, rows]);
  const postureBreakdown = useMemo(
    () => [
      {
        label: "Healthy recent signal",
        count: reportStats.healthyRecentSignal,
        note: "Recent signal with no current incident cue in the bounded view",
      },
      {
        label: "Offline posture",
        count: reportStats.offline,
        note: "Meters with no recent signal recorded",
      },
      {
        label: "Stale freshness",
        count: reportStats.stale,
        note: "Meters outside the current freshness threshold",
      },
      {
        label: "Degraded latest session",
        count: reportStats.degraded,
        note: "Latest session ended failed, timed out, or cancelled",
      },
      {
        label: "Missing endpoint context",
        count: reportStats.missingEndpoint,
        note: "Meters without a primary or active endpoint hint",
      },
    ],
    [reportStats],
  );
  const latestSessionBreakdown = useMemo(() => {
    const buckets = new Map<string, number>();
    for (const row of rows) {
      const label = buildLatestSessionBucketLabel(row.latestSession);
      buckets.set(label, (buckets.get(label) ?? 0) + 1);
    }
    return [
      "Started",
      "Succeeded",
      "Failed / timed out / cancelled",
      "No recent session",
    ].map((label) => ({
      label,
      count: buckets.get(label) ?? 0,
      note:
        label === "Failed / timed out / cancelled"
          ? "Current bounded disconnect cues from the latest session only"
          : label === "No recent session"
            ? "Meters without a latest-session record in the current overview"
            : "Latest known session posture in scope",
    }));
  }, [rows]);
  const communicationProfileBreakdown = useMemo(() => {
    const buckets = new Map<string, number>();
    for (const row of rows) {
      const label =
        row.meter.communication_profile_code ??
        row.meter.meter_profile_code ??
        "No communication summary";
      buckets.set(label, (buckets.get(label) ?? 0) + 1);
    }
    return [...buckets.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort((left, right) => {
        if (left.count !== right.count) {
          return right.count - left.count;
        }
        return left.label.localeCompare(right.label);
      })
      .slice(0, 4);
  }, [rows]);

  const overviewCards = useMemo(
    () => [
      {
        label: "Meters in result set",
        value: String(rows.length),
        note: `${totalMeters} meters currently in scope`,
      },
      {
        label: "With active endpoint hint",
        value: String(overviewStats.metersWithEndpoint),
        note: "Primary or active endpoint assignment available",
      },
      {
        label: "With recent signal",
        value: String(overviewStats.metersWithSignal),
        note: "Meters reporting a last-seen timestamp",
      },
      {
        label: "Latest session succeeded",
        value: String(overviewStats.latestSucceeded),
        note: "Most recent session closed successfully",
      },
      {
        label: "Live sessions in view",
        value: String(liveSessionStats.total),
        note: "Latest session is still started and has not ended",
      },
      {
        label: "Incident contexts",
        value: String(overviewStats.incidentCount),
        note: "Offline, stale, or degraded rows needing operator review",
      },
      {
        label: "Selected meter",
        value: selectedRow?.meter.serial_number ?? "No selection",
        note: selectedRow
          ? formatLatestSessionSummary(selectedRow.latestSession)
          : "Inspect a meter to review connectivity context",
      },
    ],
    [liveSessionStats.total, overviewStats, rows.length, selectedRow, totalMeters],
  );
  const incidentFilterSummary = useMemo(() => {
    if (incidentFilter === "all") {
      return "All incident states in the current bounded connectivity scope.";
    }

    return `Showing ${formatStatusLabel(incidentFilter).toLowerCase()} incidents only in the current bounded connectivity scope.`;
  }, [incidentFilter]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel connectivity-overview-panel">
          <div className="section-heading">
            <div>
              <h2>Connectivity operations center</h2>
              <p className="muted">
                Productized operational visibility into current meter, endpoint, and
                recent session context using the existing connectivity read model.
              </p>
            </div>
            <span className="artifact-pill">{totalMeters} meters in scope</span>
          </div>

          {isLoadingOverview ? (
            <p className="muted">Loading connectivity overview...</p>
          ) : null}

          {!isLoadingOverview ? (
            <div className="connectivity-overview-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card connectivity-overview-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        <section className="subpanel" id="connectivity-reports-workspace">
          <div className="section-heading">
            <div>
              <h2>Connectivity reports workspace</h2>
              <p className="muted">
                Current-state reporting for fleet communication posture using the existing
                connectivity overview, latest-session, and freshness signals.
              </p>
            </div>
            <span className="artifact-pill">{rows.length} meters summarized</span>
          </div>

          {isLoadingOverview ? (
            <p className="muted">Loading connectivity reports workspace...</p>
          ) : rows.length === 0 ? (
            <p className="muted">No connectivity reports are available in the bounded scope.</p>
          ) : (
            <div className="detail-stack">
              <div className="connectivity-overview-grid">
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">Healthy recent signal</span>
                  <strong>{String(reportStats.healthyRecentSignal)}</strong>
                  <p className="muted">Meters with recent signal and no current incident cue</p>
                </div>
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">Offline posture</span>
                  <strong>{String(reportStats.offline)}</strong>
                  <p className="muted">Meters currently missing a recent signal</p>
                </div>
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">Stale freshness</span>
                  <strong>{String(reportStats.stale)}</strong>
                  <p className="muted">Meters beyond the bounded freshness window</p>
                </div>
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">Disconnect cues</span>
                  <strong>{String(reportStats.disconnectCues)}</strong>
                  <p className="muted">Latest failed, timed out, or cancelled sessions</p>
                </div>
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">Live sessions in reporting scope</span>
                  <strong>{String(liveSessionStats.total)}</strong>
                  <p className="muted">Latest sessions still started with no recorded end</p>
                </div>
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">No recent session context</span>
                  <strong>{String(reportStats.noRecentSession)}</strong>
                  <p className="muted">Meters without a latest-session record in the current view</p>
                </div>
              </div>

              <div className="artifact-row">
                <span className="artifact-pill">
                  Bounded report uses current latest-session and last-seen context; no historical
                  trendline is modeled here.
                </span>
                <Link className="nav-link" href="#connectivity-live-sessions-workspace">
                  Review live sessions
                </Link>
                <Link className="nav-link" href="#connectivity-incidents-workspace">
                  Review incidents
                </Link>
              </div>

              <div className="connectivity-module-layout">
                <section className="subpanel">
                  <div className="section-heading">
                    <div>
                      <h3>Fleet posture breakdown</h3>
                      <p className="muted">
                        Current posture counts derived directly from the bounded connectivity
                        result set.
                      </p>
                    </div>
                  </div>

                  <div className="command-list">
                    {postureBreakdown.map((item) => (
                      <article key={item.label} className="command-list-item">
                        <div className="command-list-item-header">
                          <strong>{item.label}</strong>
                          <span className="artifact-pill">{item.count} meters</span>
                        </div>
                        <div className="command-list-item-meta">
                          <span>{item.note}</span>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="subpanel">
                  <div className="section-heading">
                    <div>
                      <h3>Latest session breakdown</h3>
                      <p className="muted">
                        Latest known session posture per meter, without historical rollups.
                      </p>
                    </div>
                  </div>

                  <div className="command-list">
                    {latestSessionBreakdown.map((item) => (
                      <article key={item.label} className="command-list-item">
                        <div className="command-list-item-header">
                          <strong>{item.label}</strong>
                          <span className="artifact-pill">{item.count} meters</span>
                        </div>
                        <div className="command-list-item-meta">
                          <span>{item.note}</span>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
              </div>

              <section className="subpanel">
                <div className="section-heading">
                  <div>
                    <h3>Communication context in scope</h3>
                    <p className="muted">
                      Top communication profile or meter profile contexts visible in the current
                      bounded reporting scope.
                    </p>
                  </div>
                </div>

                <div className="command-list">
                  {communicationProfileBreakdown.map((item) => (
                    <article key={item.label} className="command-list-item">
                      <div className="command-list-item-header">
                        <strong>{item.label}</strong>
                        <span className="artifact-pill">{item.count} meters</span>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          )}
        </section>

        <section className="subpanel" id="connectivity-live-sessions-workspace">
          <div className="section-heading">
            <div>
              <h2>Connectivity live sessions workspace</h2>
              <p className="muted">
                Active session visibility using the current latest-session read model for each
                meter in scope.
              </p>
            </div>
            <span className="artifact-pill">{liveSessionRows.length} live sessions</span>
          </div>

          {isLoadingOverview ? (
            <p className="muted">Loading live sessions workspace...</p>
          ) : (
            <div className="detail-stack">
              <div className="connectivity-overview-grid">
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">Live sessions in view</span>
                  <strong>{String(liveSessionStats.total)}</strong>
                  <p className="muted">Latest session is still active</p>
                </div>
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">With recent signal</span>
                  <strong>{String(liveSessionStats.withRecentSignal)}</strong>
                  <p className="muted">Active sessions with fresh last-seen context</p>
                </div>
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">With endpoint context</span>
                  <strong>{String(liveSessionStats.withEndpoint)}</strong>
                  <p className="muted">Active sessions with a primary or active endpoint hint</p>
                </div>
              </div>

              <div className="command-list">
                {liveSessionRows.length === 0 ? (
                  <p className="muted">
                    No active connectivity sessions are currently visible in the bounded scope.
                  </p>
                ) : null}

                {liveSessionRows.map((row) => {
                  const freshnessContext = getFreshnessContext(row.meter.last_seen_at);
                  const healthLabel = buildSessionHealthLabel(row.latestSession, freshnessContext);
                  const healthTone = buildSessionHealthTone(freshnessContext);
                  return (
                    <article key={row.meter.id} className="command-list-item">
                      <div className="command-list-item-header">
                        <strong>{row.meter.serial_number}</strong>
                        <span className={`status-pill ${buildStatusTone(row.latestSession?.status ?? null)}`}>
                          {row.latestSession
                            ? `Session ${formatStatusLabel(row.latestSession.status)}`
                            : "No recent session"}
                        </span>
                      </div>
                      <div className="command-list-item-badges">
                        <span className={`status-pill ${freshnessContext.tone}`}>
                          {freshnessContext.label}
                        </span>
                        <span className={`status-pill ${healthTone}`}>
                          {healthLabel}
                        </span>
                        <span className="artifact-pill">
                          {row.primaryEndpoint?.endpoint_display_name ??
                            row.primaryEndpoint?.endpoint_code ??
                            "No active endpoint"}
                        </span>
                      </div>
                      <div className="command-list-item-meta">
                        <span>
                          {row.latestSession
                            ? `${formatStatusLabel(row.latestSession.session_purpose)} session`
                            : "No recent session"}
                        </span>
                        <span>Started {formatDateTime(row.latestSession?.started_at ?? null)}</span>
                      </div>
                      <div className="command-list-item-meta">
                        <span>
                          {row.meter.communication_profile_code ??
                            row.meter.meter_profile_code ??
                            "No communication summary"}
                        </span>
                        <span>Last seen {formatDateTime(row.meter.last_seen_at)}</span>
                      </div>
                      <div className="artifact-row">
                        <button
                          className="secondary-button"
                          onClick={() => setSelectedMeterId(row.meter.id)}
                          type="button"
                        >
                          Inspect live session
                        </button>
                        <Link className="secondary-button" href={`/meters/${row.meter.id}`}>
                          Open meter detail
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            </div>
          )}
        </section>

        <section className="subpanel" id="connectivity-incidents-workspace">
          <div className="section-heading">
            <div>
              <h2>Offline meters / connectivity incidents</h2>
              <p className="muted">
                Derived operational review queue for meters with no recent signal, stale
                freshness, or a recent failed connectivity session.
              </p>
            </div>
            <span className="artifact-pill">{filteredIncidentRows.length} incident contexts</span>
          </div>

          <div className="artifact-row">
            <span className="artifact-pill">
              Offline and stale contexts stay bounded to the current connectivity result set.
            </span>
            <span className="artifact-pill">
              Inspect an incident here, then continue into existing meter detail when needed.
            </span>
          </div>

          <div className="artifact-row">
            <button
              className={incidentFilter === "all" ? "primary-button" : "secondary-button"}
              onClick={() => setIncidentFilter("all")}
              type="button"
            >
              All incidents
            </button>
            <button
              className={incidentFilter === "offline" ? "primary-button" : "secondary-button"}
              onClick={() => setIncidentFilter("offline")}
              type="button"
            >
              Offline
            </button>
            <button
              className={incidentFilter === "stale" ? "primary-button" : "secondary-button"}
              onClick={() => setIncidentFilter("stale")}
              type="button"
            >
              Stale
            </button>
            <button
              className={incidentFilter === "degraded" ? "primary-button" : "secondary-button"}
              onClick={() => setIncidentFilter("degraded")}
              type="button"
            >
              Degraded
            </button>
          </div>

          <p className="muted">{incidentFilterSummary}</p>

          {!isLoadingOverview ? (
            <div className="detail-stack">
              <div className="connectivity-overview-grid">
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">Visible incidents</span>
                  <strong>{String(incidentStats.visible)}</strong>
                  <p className="muted">Current offline or degraded contexts in the selected filter</p>
                </div>
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">Offline posture</span>
                  <strong>{String(incidentStats.offline)}</strong>
                  <p className="muted">Meters with no recent signal recorded</p>
                </div>
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">Stale freshness</span>
                  <strong>{String(incidentStats.stale)}</strong>
                  <p className="muted">Meters outside the bounded freshness window</p>
                </div>
                <div className="stat-card connectivity-overview-card">
                  <span className="stat-label">Disconnect cues</span>
                  <strong>{String(incidentStats.disconnectCues)}</strong>
                  <p className="muted">Latest failed, timed out, or cancelled sessions in view</p>
                </div>
              </div>

              <div className="artifact-row">
                <span className="artifact-pill">
                  No repeated disconnect history is modeled here; the latest failed session is the
                  current bounded disconnect cue.
                </span>
                <span className="artifact-pill">
                  {incidentStats.withoutEndpoint} incident contexts currently have no active
                  endpoint assignment.
                </span>
              </div>

              {selectedIncidentRow ? (
                <section className="connectivity-detail-hero">
                  <div className="connectivity-detail-title-row">
                    <div>
                      <p className="eyebrow">Incident Troubleshooting Workspace</p>
                      <h3>{selectedIncidentRow.row.meter.serial_number}</h3>
                      <p className="muted">
                        {buildIncidentPostureLabel(
                          selectedIncidentRow.row,
                          selectedIncidentRow.freshnessContext,
                          selectedIncidentRow.incident,
                        )}
                      </p>
                    </div>
                    <span
                      className={`status-pill ${buildStatusTone(selectedIncidentRow.incident.state)}`}
                    >
                      {formatStatusLabel(selectedIncidentRow.incident.state)}
                    </span>
                  </div>

                  <div className="connectivity-row-badges">
                    <span
                      className={`status-pill ${buildSeverityTone(
                        selectedIncidentRow.incident.severity,
                      )}`}
                    >
                      Severity {formatStatusLabel(selectedIncidentRow.incident.severity)}
                    </span>
                    <span className={`status-pill ${selectedIncidentRow.freshnessContext.tone}`}>
                      {selectedIncidentRow.freshnessContext.label}
                    </span>
                    <span className="artifact-pill">
                      {buildDisconnectCue(selectedIncidentRow.row.latestSession)}
                    </span>
                    <span className="artifact-pill">
                      {selectedIncidentRow.row.primaryEndpoint?.endpoint_display_name ??
                        selectedIncidentRow.row.primaryEndpoint?.endpoint_code ??
                        "No active endpoint"}
                    </span>
                  </div>

                  <div className="detail-grid">
                    <div className="stat-card">
                      <span className="stat-label">Incident summary</span>
                      <strong>{selectedIncidentRow.incident.summary}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Last seen</span>
                      <strong>{formatDateTime(selectedIncidentRow.row.meter.last_seen_at)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Latest session</span>
                      <strong>{formatLatestSessionSummary(selectedIncidentRow.row.latestSession)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Session started</span>
                      <strong>
                        {formatDateTime(selectedIncidentRow.row.latestSession?.started_at ?? null)}
                      </strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Protocol summary</span>
                      <strong>
                        {selectedIncidentRow.row.meter.communication_profile_code ??
                          selectedIncidentRow.row.meter.meter_profile_code ??
                          "No communication summary"}
                      </strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Utility meter number</span>
                      <strong>
                        {selectedIncidentRow.row.meter.utility_meter_number ?? "Not available"}
                      </strong>
                    </div>
                  </div>

                  <div className="artifact-row">
                    <button
                      className="secondary-button"
                      onClick={() => setSelectedMeterId(selectedIncidentRow.row.meter.id)}
                      type="button"
                    >
                      Inspect incident detail
                    </button>
                    <Link className="nav-link" href={`/meters/${selectedIncidentRow.row.meter.id}`}>
                      Open meter detail
                    </Link>
                  </div>
                </section>
              ) : null}
            </div>
          ) : null}

          {isLoadingOverview ? (
            <p className="muted">Loading offline meters and connectivity incidents...</p>
          ) : null}

          <div className="meter-list">
            {!isLoadingOverview && filteredIncidentRows.length === 0 ? (
              <p className="muted">
                {incidentFilter === "all"
                  ? "No offline meters or connectivity incidents match the current bounded scope."
                  : `No ${incidentFilter} incidents match the current bounded scope.`}
              </p>
            ) : null}

            {filteredIncidentRows.map(({ row, freshnessContext, incident }) => (
              <article
                key={`incident-${row.meter.id}`}
                className={
                  selectedMeterId === row.meter.id
                    ? "meter-list-item connectivity-list-item selected"
                    : "meter-list-item connectivity-list-item"
                }
              >
                <div className="command-list-item-header">
                  <strong>{row.meter.serial_number}</strong>
                  <div className="artifact-row">
                    <span className={`status-pill ${buildStatusTone(incident.state)}`}>
                      {formatStatusLabel(incident.state)}
                    </span>
                    <span className={`status-pill ${buildSeverityTone(incident.severity)}`}>
                      Severity {formatStatusLabel(incident.severity)}
                    </span>
                  </div>
                </div>

                <div className="connectivity-row-badges">
                  <span className={`status-pill ${freshnessContext.tone}`}>
                    {freshnessContext.label}
                  </span>
                  <span className={`status-pill ${buildStatusTone(row.latestSession?.status ?? null)}`}>
                    {row.latestSession
                      ? `Latest session ${formatStatusLabel(row.latestSession.status)}`
                      : "No recent session"}
                  </span>
                  <span className="artifact-pill">
                    {row.primaryEndpoint?.endpoint_display_name ??
                      row.primaryEndpoint?.endpoint_code ??
                      "No active endpoint"}
                  </span>
                </div>

                <div className="command-list-item-meta">
                  <span>Meter ID {row.meter.id}</span>
                  <span>{incident.summary}</span>
                </div>
                <div className="command-list-item-meta">
                  <span>{formatLatestSessionSummary(row.latestSession)}</span>
                  <span>Last seen {formatDateTime(row.meter.last_seen_at)}</span>
                </div>

                <div className="connectivity-row-actions">
                  <button
                    className="secondary-button"
                    onClick={() => setSelectedMeterId(row.meter.id)}
                    type="button"
                  >
                    Inspect incident
                  </button>
                  <Link className="nav-link" href={`/meters/${row.meter.id}`}>
                    Open meter detail
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </section>

        <div className="connectivity-module-layout">
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Connectivity-focused meters</h2>
                <p className="muted">
                  Inspect a bounded summary here, then continue into the existing meter
                  details operational page when deeper context is needed.
                </p>
              </div>
            </div>

            {isLoadingOverview ? (
              <p className="muted">Loading connectivity-focused meters...</p>
            ) : null}

            <div className="meter-list">
              {!isLoadingOverview && rows.length === 0 ? (
                <p className="muted">No connectivity overview items available.</p>
              ) : null}

              {rows.map((row) => (
                <article
                  key={row.meter.id}
                  className={
                    selectedMeterId === row.meter.id
                      ? "meter-list-item connectivity-list-item selected"
                      : "meter-list-item connectivity-list-item"
                  }
                >
                  <div className="command-list-item-header">
                    <strong>{row.meter.serial_number}</strong>
                    <span className={`status-pill ${buildStatusTone(row.meter.current_status)}`}>
                      {formatStatusLabel(row.meter.current_status)}
                    </span>
                  </div>

                  <div className="connectivity-row-badges">
                    <span className={`status-pill ${buildStatusTone(row.latestSession?.status ?? null)}`}>
                      {row.latestSession
                        ? formatStatusLabel(row.latestSession.status)
                        : "No recent session"}
                    </span>
                    <span className="artifact-pill">{formatFreshnessHint(row.meter.last_seen_at)}</span>
                    <span className="artifact-pill">
                      {row.meter.communication_profile_code ??
                        row.meter.meter_profile_code ??
                        "No communication summary"}
                    </span>
                  </div>

                  <div className="command-list-item-meta">
                    <span>Meter ID {row.meter.id}</span>
                    <span>
                      {row.primaryEndpoint?.endpoint_display_name ??
                        row.primaryEndpoint?.endpoint_code ??
                        "No active endpoint"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{formatLatestSessionSummary(row.latestSession)}</span>
                    <span>Last seen {formatDateTime(row.meter.last_seen_at)}</span>
                  </div>

                  <div className="connectivity-row-actions">
                    <button
                      className="secondary-button"
                      onClick={() => setSelectedMeterId(row.meter.id)}
                      type="button"
                    >
                      Inspect summary
                    </button>
                    <Link className="nav-link" href={`/meters/${row.meter.id}`}>
                      Open meter detail
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Connectivity detail</h2>
                <p className="muted">
                  Bounded meter, endpoint, and recent session summary for the selected
                  connectivity row.
                </p>
              </div>
            </div>

            {selectedRow ? (
              <div className="detail-stack">
                <section className="connectivity-detail-hero">
                  <div className="connectivity-detail-title-row">
                    <div>
                      <p className="eyebrow">Selected Meter</p>
                      <h3>{selectedRow.meter.serial_number}</h3>
                      <p className="muted">
                        Current status {formatStatusLabel(selectedRow.meter.current_status)} with{" "}
                        {selectedRow.primaryEndpoint ? "an endpoint assignment" : "no active endpoint"}{" "}
                        and {selectedRow.latestSession ? "a recent session record" : "no recent session"}.
                      </p>
                    </div>
                    <span
                      className={`status-pill ${buildStatusTone(selectedRow.meter.current_status)}`}
                    >
                      {formatStatusLabel(selectedRow.meter.current_status)}
                    </span>
                  </div>

                  <div className="connectivity-row-badges">
                    {selectedRowIncident ? (
                      <>
                        <span className={`status-pill ${buildStatusTone(selectedRowIncident.state)}`}>
                          Incident {formatStatusLabel(selectedRowIncident.state)}
                        </span>
                        <span
                          className={`status-pill ${buildSeverityTone(selectedRowIncident.severity)}`}
                        >
                          Severity {formatStatusLabel(selectedRowIncident.severity)}
                        </span>
                      </>
                    ) : null}
                    <span className="artifact-pill">
                      {selectedRowFreshnessContext?.label ??
                        formatFreshnessHint(selectedRow.meter.last_seen_at)}
                    </span>
                    <span className="artifact-pill">
                      {selectedRow.primaryEndpoint?.assignment_status
                        ? `Endpoint ${formatStatusLabel(selectedRow.primaryEndpoint.assignment_status)}`
                        : "No endpoint assignment"}
                    </span>
                    <span className="artifact-pill">
                      {selectedRow.latestSession
                        ? `Session ${formatStatusLabel(selectedRow.latestSession.status)}`
                        : "No recent session"}
                    </span>
                  </div>
                </section>

                <div className="detail-grid">
                  <div className="stat-card">
                    <span className="stat-label">Meter ID</span>
                    <strong>{selectedRow.meter.id}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Utility meter number</span>
                    <strong>{selectedRow.meter.utility_meter_number ?? "Not available"}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Manufacturer / model</span>
                    <strong>
                      {selectedRow.meter.manufacturer_code} / {selectedRow.meter.meter_model_code}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Protocol summary</span>
                    <strong>
                      {selectedRow.meter.communication_profile_code ??
                        selectedRow.meter.meter_profile_code ??
                        "No communication summary"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Primary endpoint</span>
                    <strong>
                      {selectedRow.primaryEndpoint?.endpoint_display_name ??
                        selectedRow.primaryEndpoint?.endpoint_code ??
                        "No active endpoint"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Latest session summary</span>
                    <strong>{formatLatestSessionSummary(selectedRow.latestSession)}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Session started</span>
                    <strong>{formatDateTime(selectedRow.latestSession?.started_at ?? null)}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Session ended</span>
                    <strong>{formatDateTime(selectedRow.latestSession?.ended_at ?? null)}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Last seen</span>
                    <strong>{formatDateTime(selectedRow.meter.last_seen_at)}</strong>
                  </div>
                </div>

                <div className="connectivity-row-actions">
                  <button
                    className="secondary-button"
                    onClick={() => void loadConnectivityOverview()}
                    type="button"
                  >
                    Refresh overview
                  </button>
                  <Link className="nav-link" href={`/meters/${selectedRow.meter.id}`}>
                    Open meter detail
                  </Link>
                </div>
              </div>
            ) : (
              <p className="muted">Select a connectivity-focused meter to inspect its summary.</p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
