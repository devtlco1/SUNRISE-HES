"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ActionTile,
  DataTableShell,
  StatCard,
  StatusChip,
  SummaryList,
  SurfaceCard,
  formatDateTime,
  formatStatusLabel,
  getStatusTone,
  type StatusTone,
} from "./operational-ui";
import type { AuthorizedFetch } from "./operational-shell";
import { FourCircleIcon, HomeIcon, PieChartIcon, TableIcon, UserIcon } from "./nextadmin-icons";

type MeterListItem = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  manufacturer_code: string;
  meter_model_code: string;
  communication_profile_code: string | null;
  meter_profile_code: string | null;
  firmware_version: string | null;
  current_status: string;
  transformer_id: string | null;
  service_point_id: string | null;
  last_seen_at: string | null;
  is_active: boolean;
};

type MeterListResponse = {
  total: number;
  items: MeterListItem[];
};

type CommandRecentItem = {
  command_id: string;
  command_family: string;
  command_status: string;
  meter_id: string;
  command_template_code: string;
  family_specific_outcome_summary: Record<string, string | null>;
  latest_updated_at: string;
};

type CommandRecentListResponse = {
  total: number;
  items: CommandRecentItem[];
};

type RecentEventItem = {
  id: string;
  meter_id: string | null;
  event_code: string;
  event_name: string | null;
  severity: string;
  event_state: string;
  occurred_at: string;
  received_at: string;
};

type RecentEventListResponse = {
  total: number;
  items: RecentEventItem[];
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

type MeterReadingItem = {
  id: string;
  captured_at: string;
  quality?: string | null;
};

type MeterReadingListResponse = {
  total: number;
  items: MeterReadingItem[];
};

type GisLiteEntity = {
  meter_id: string;
  meter_status: string;
  meter_last_seen_at: string | null;
  service_point_id: string | null;
  service_point_code: string | null;
  has_coordinates: boolean;
  subscriber_display_name: string | null;
  account_number: string | null;
  location_presence: "coordinates_available" | "service_point_only" | "unlinked";
};

type GisLiteEntityListResponse = {
  total: number;
  items: GisLiteEntity[];
};

type DashboardSnapshot = {
  totalMeters: number;
  visibleMeters: MeterListItem[];
  recentCommands: CommandRecentItem[];
  pendingApprovals: CommandRecentItem[];
  recentEvents: RecentEventItem[];
  recentSessionsByMeterId: Record<string, ConnectivitySession | null>;
  recentReadingsByMeterId: Record<string, MeterReadingItem | null>;
  gisByMeterId: Record<string, GisLiteEntity | null>;
};

type AttentionQueueItem = {
  id: string;
  label: string;
  count: number;
  summary: string;
  href: string;
  action: string;
  tone: StatusTone;
};

const STALE_SIGNAL_THRESHOLD_MS = 1000 * 60 * 60 * 24;

function formatFamilySummary(item: Record<string, string | null>): string {
  if ("terminal_status_category" in item) {
    return item.terminal_status_category ?? "No terminal outcome";
  }
  if ("relay_control_operation" in item) {
    const operation = item.relay_control_operation ?? "relay";
    const outcome = item.relay_control_execution_outcome ?? "pending";
    return `${operation} (${outcome})`;
  }
  if ("on_demand_read_operation" in item) {
    const operation = item.on_demand_read_operation ?? "read";
    const snapshotType = item.snapshot_type ?? "snapshot";
    const outcome = item.on_demand_read_execution_outcome ?? "pending";
    return `${operation} ${snapshotType} (${outcome})`;
  }
  return "No operational summary";
}

function formatAgeLabel(value: string | null): string {
  if (!value) {
    return "No signal";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return formatDateTime(value);
  }

  const ageMs = Date.now() - date.getTime();
  const ageHours = Math.floor(ageMs / (1000 * 60 * 60));
  if (ageHours < 1) {
    return "Within the last hour";
  }
  if (ageHours < 24) {
    return `${ageHours}h ago`;
  }
  return `${Math.floor(ageHours / 24)}d ago`;
}

function buildSignalState(
  lastSeenAt: string | null,
  latestSession: ConnectivitySession | null,
): { label: string; tone: StatusTone } {
  if (!lastSeenAt) {
    return { label: "Offline", tone: "danger" };
  }

  const date = new Date(lastSeenAt);
  if (Number.isNaN(date.getTime())) {
    return { label: "Unknown", tone: "neutral" };
  }

  const ageMs = Date.now() - date.getTime();
  if (latestSession && ["failed", "timed_out", "cancelled"].includes(latestSession.status)) {
    return { label: "Degraded", tone: "warning" };
  }
  if (ageMs >= STALE_SIGNAL_THRESHOLD_MS) {
    return { label: "Stale", tone: "warning" };
  }
  return { label: "Online", tone: "positive" };
}

export function OperationalHomeModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const loadOverview = useCallback(async () => {
    setIsLoading(true);
    setPageError(null);

    try {
      const [metersResult, recentCommandsResult, pendingApprovalsResult, recentEventsResult] =
        await Promise.allSettled([
          authorizedFetch<MeterListResponse>("/api/v1/meters?offset=0&limit=20"),
          authorizedFetch<CommandRecentListResponse>("/api/v1/commands/recent?limit=12"),
          authorizedFetch<CommandRecentListResponse>("/api/v1/commands/approvals/pending?limit=20"),
          authorizedFetch<RecentEventListResponse>("/api/v1/events/recent?limit=20"),
        ]);

      if (metersResult.status !== "fulfilled") {
        throw metersResult.reason instanceof Error
          ? metersResult.reason
          : new Error("Unable to load dashboard meters.");
      }

      const visibleMeters = metersResult.value.items;
      const [sessionsResults, readingsResults, gisResults] = await Promise.all([
        Promise.allSettled(
          visibleMeters.map((meter) =>
            authorizedFetch<ConnectivitySessionHistoryListResponse>(
              `/api/v1/meters/${meter.id}/sessions?limit=1`,
            ),
          ),
        ),
        Promise.allSettled(
          visibleMeters.map((meter) =>
            authorizedFetch<MeterReadingListResponse>(`/api/v1/meters/${meter.id}/readings?limit=1`),
          ),
        ),
        Promise.allSettled(
          visibleMeters.map((meter) =>
            authorizedFetch<GisLiteEntityListResponse>(
              `/api/v1/gis-lite/entities?limit=1&meter_id=${meter.id}`,
            ),
          ),
        ),
      ]);

      const recentSessionsByMeterId: Record<string, ConnectivitySession | null> = {};
      const recentReadingsByMeterId: Record<string, MeterReadingItem | null> = {};
      const gisByMeterId: Record<string, GisLiteEntity | null> = {};

      visibleMeters.forEach((meter, index) => {
        recentSessionsByMeterId[meter.id] =
          sessionsResults[index]?.status === "fulfilled"
            ? sessionsResults[index].value.items[0] ?? null
            : null;
        recentReadingsByMeterId[meter.id] =
          readingsResults[index]?.status === "fulfilled"
            ? readingsResults[index].value.items[0] ?? null
            : null;
        gisByMeterId[meter.id] =
          gisResults[index]?.status === "fulfilled" ? gisResults[index].value.items[0] ?? null : null;
      });

      setSnapshot({
        totalMeters: metersResult.value.total,
        visibleMeters,
        recentCommands:
          recentCommandsResult.status === "fulfilled" ? recentCommandsResult.value.items : [],
        pendingApprovals:
          pendingApprovalsResult.status === "fulfilled" ? pendingApprovalsResult.value.items : [],
        recentEvents:
          recentEventsResult.status === "fulfilled" ? recentEventsResult.value.items : [],
        recentSessionsByMeterId,
        recentReadingsByMeterId,
        gisByMeterId,
      });

      const partialFailures = [
        recentCommandsResult,
        pendingApprovalsResult,
        recentEventsResult,
        ...sessionsResults,
        ...readingsResults,
        ...gisResults,
      ].some((result) => result.status === "rejected");

      if (partialFailures) {
        setPageError("Some dashboard context could not be loaded.");
      }
    } catch (error) {
      setSnapshot(null);
      setPageError(
        error instanceof Error ? error.message : "Unable to load dashboard context.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [authorizedFetch]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  const dashboardMetrics = useMemo(() => {
    if (!snapshot) {
      return [];
    }

    const visibleSignals = snapshot.visibleMeters.map((meter) =>
      buildSignalState(meter.last_seen_at, snapshot.recentSessionsByMeterId[meter.id] ?? null),
    );
    const onlineCount = visibleSignals.filter((item) => item.label === "Online").length;
    const offlineCount = visibleSignals.filter((item) => item.label === "Offline").length;
    const warningCount = visibleSignals.filter((item) => item.tone === "warning").length;
    const mappedCount = Object.values(snapshot.gisByMeterId).filter(
      (entity) => entity?.has_coordinates,
    ).length;
    const criticalAlarmCount = snapshot.recentEvents.filter((event) =>
      ["critical", "major"].includes(event.severity.toLowerCase()),
    ).length;

    return [
      {
        label: "Fleet meters",
        value: String(snapshot.totalMeters),
        note: `${snapshot.visibleMeters.length} meters reviewed in the current dashboard scope`,
        tone: "neutral" as const,
        icon: TableIcon,
      },
      {
        label: "Online in current scope",
        value: String(onlineCount),
        note: `${offlineCount} offline and ${warningCount} stale or degraded`,
        tone: onlineCount > 0 ? ("positive" as const) : ("warning" as const),
        icon: PieChartIcon,
      },
      {
        label: "Pending approvals",
        value: String(snapshot.pendingApprovals.length),
        note: "Approval-gated remote actions awaiting review",
        tone:
          snapshot.pendingApprovals.length > 0 ? ("warning" as const) : ("neutral" as const),
        icon: FourCircleIcon,
      },
      {
        label: "Recent alarms",
        value: String(snapshot.recentEvents.length),
        note: `${criticalAlarmCount} critical or major in the recent event feed`,
        tone: criticalAlarmCount > 0 ? ("danger" as const) : ("info" as const),
        icon: UserIcon,
      },
      {
        label: "Meters with recent reads",
        value: String(
          Object.values(snapshot.recentReadingsByMeterId).filter((reading) => reading !== null)
            .length,
        ),
        note: `${
          Object.values(snapshot.recentReadingsByMeterId).filter((reading) => reading === null)
            .length
        } meters without a recent read`,
        tone: "info" as const,
        icon: HomeIcon,
      },
      {
        label: "GIS mapped in scope",
        value: String(mappedCount),
        note: `${
          Object.values(snapshot.gisByMeterId).filter(
            (entity) => entity?.location_presence === "service_point_only",
          ).length
        } service-point-only records`,
        tone: mappedCount > 0 ? ("positive" as const) : ("warning" as const),
        icon: TableIcon,
      },
    ];
  }, [snapshot]);

  const connectivitySummary = useMemo(() => {
    if (!snapshot) {
      return null;
    }

    const signals = snapshot.visibleMeters.map((meter) =>
      buildSignalState(meter.last_seen_at, snapshot.recentSessionsByMeterId[meter.id] ?? null),
    );

    return {
      online: signals.filter((item) => item.label === "Online").length,
      offline: signals.filter((item) => item.label === "Offline").length,
      warning: signals.filter((item) => item.tone === "warning").length,
      priorityMeters: snapshot.visibleMeters
        .map((meter) => ({
          meter,
          signal: buildSignalState(meter.last_seen_at, snapshot.recentSessionsByMeterId[meter.id] ?? null),
          latestSession: snapshot.recentSessionsByMeterId[meter.id] ?? null,
        }))
        .filter((item) => item.signal.tone !== "positive")
        .slice(0, 5),
    };
  }, [snapshot]);

  const commandSummary = useMemo(() => {
    if (!snapshot) {
      return null;
    }

    return {
      queued: snapshot.recentCommands.filter((command) =>
        command.command_status.toLowerCase().includes("queue"),
      ).length,
      failed: snapshot.recentCommands.filter((command) =>
        ["failed", "timed_out", "cancelled"].includes(command.command_status),
      ).length,
      succeeded: snapshot.recentCommands.filter((command) =>
        command.command_status.toLowerCase().includes("succeed") ||
        command.command_status.toLowerCase().includes("complete"),
      ).length,
      pendingApprovals: snapshot.pendingApprovals.length,
    };
  }, [snapshot]);

  const alarmSummary = useMemo(() => {
    if (!snapshot) {
      return null;
    }

    return {
      critical: snapshot.recentEvents.filter((event) => event.severity === "critical").length,
      major: snapshot.recentEvents.filter((event) => event.severity === "major").length,
      warning: snapshot.recentEvents.filter((event) =>
        ["warning", "minor"].includes(event.severity),
      ).length,
      open: snapshot.recentEvents.filter((event) =>
        ["new", "acknowledged", "in_investigation"].includes(event.event_state),
      ).length,
    };
  }, [snapshot]);

  const readingSummary = useMemo(() => {
    if (!snapshot) {
      return null;
    }

    const readings = Object.values(snapshot.recentReadingsByMeterId);
    return {
      captured: readings.filter((reading) => reading !== null).length,
      missing: readings.filter((reading) => reading === null).length,
      flagged: readings.filter(
        (reading) => Boolean(reading?.quality) && !["actual", "valid"].includes(String(reading?.quality)),
      ).length,
    };
  }, [snapshot]);

  const gisSummary = useMemo(() => {
    if (!snapshot) {
      return null;
    }

    const items = Object.values(snapshot.gisByMeterId);
    return {
      mapped: items.filter((item) => item?.has_coordinates).length,
      servicePointOnly: items.filter((item) => item?.location_presence === "service_point_only")
        .length,
      unlinked: items.filter((item) => item?.location_presence === "unlinked").length,
      linkedAccounts: items.filter((item) => item?.account_number).length,
    };
  }, [snapshot]);

  const attentionQueue = useMemo<AttentionQueueItem[]>(() => {
    if (!snapshot || !connectivitySummary || !readingSummary) {
      return [];
    }

    const items: AttentionQueueItem[] = [];

    if (snapshot.pendingApprovals.length > 0) {
      items.push({
        id: "pending-approvals",
        label: "Pending approvals",
        count: snapshot.pendingApprovals.length,
        summary: "Command approvals are waiting for operator review.",
        href: "/commands?tab=approvals",
        action: "Review queue",
        tone: "warning",
      });
    }

    if (connectivitySummary.offline > 0 || connectivitySummary.warning > 0) {
      items.push({
        id: "connectivity",
        label: "Connectivity review",
        count: connectivitySummary.offline + connectivitySummary.warning,
        summary: "Meters in the current scope are offline, stale, or degraded.",
        href: "/connectivity",
        action: "Open connectivity",
        tone: "danger",
      });
    }

    if (readingSummary.missing > 0) {
      items.push({
        id: "readings",
        label: "Reading gaps",
        count: readingSummary.missing,
        summary: "Meters are visible without a recent reading.",
        href: "/readings",
        action: "Open readings",
        tone: "warning",
      });
    }

    if (snapshot.recentEvents.length > 0) {
      items.push({
        id: "alarms",
        label: "Active alarm feed",
        count: snapshot.recentEvents.length,
        summary: "Recent events and alarms require triage from the monitoring surface.",
        href: "/jobs-events-alerts",
        action: "Open monitoring",
        tone: "info",
      });
    }

    return items.slice(0, 4);
  }, [connectivitySummary, readingSummary, snapshot]);

  if (isLoading && !snapshot) {
    return (
      <div className="hes-page-stack">
        <div className="hes-stat-grid">
          {["Fleet meters", "Online in current scope", "Pending approvals", "Recent alarms"].map(
            (label) => (
              <StatCard key={label} label={label} note="Loading dashboard..." tone="neutral" value="..." />
            ),
          )}
        </div>
        <SurfaceCard title="Connectivity summary" description="Loading dashboard context...">
          <p className="muted">Loading dashboard context...</p>
        </SurfaceCard>
      </div>
    );
  }

  return (
    <div className="hes-page-stack">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="hes-stat-grid">
        {dashboardMetrics.map((metric) => (
          <StatCard
            key={metric.label}
            icon={metric.icon}
            label={metric.label}
            note={metric.note}
            tone={metric.tone}
            value={metric.value}
          />
        ))}
      </div>

      <div className="hes-dashboard-grid">
        <div className="hes-dashboard-main">
          <SurfaceCard
            title="Connectivity summary"
            description="Current dashboard scope of meter signal health and recent session posture."
            aside={<Link className="secondary-button" href="/connectivity">Open connectivity</Link>}
          >
            {connectivitySummary ? (
              <div className="hes-card-body-grid">
                <SummaryList
                  items={[
                    { label: "Online", value: String(connectivitySummary.online), tone: "positive" },
                    { label: "Offline", value: String(connectivitySummary.offline), tone: "danger" },
                    {
                      label: "Stale / degraded",
                      value: String(connectivitySummary.warning),
                      tone: "warning",
                    },
                  ]}
                />
                <div className="hes-queue-list">
                  {connectivitySummary.priorityMeters.length === 0 ? (
                    <p className="muted">No priority connectivity exceptions in the current scope.</p>
                  ) : (
                    connectivitySummary.priorityMeters.map((item) => (
                      <article key={item.meter.id} className="hes-queue-item">
                        <div>
                          <strong>{item.meter.serial_number}</strong>
                          <p>
                            {item.latestSession
                              ? `${formatStatusLabel(item.latestSession.status)} session`
                              : "No recent session"}{" "}
                            · {formatAgeLabel(item.meter.last_seen_at)}
                          </p>
                        </div>
                        <StatusChip label={item.signal.label} tone={item.signal.tone} />
                      </article>
                    ))
                  )}
                </div>
              </div>
            ) : (
              <p className="muted">Connectivity summary is not available.</p>
            )}
          </SurfaceCard>

          <div className="hes-two-column-grid">
            <DataTableShell
              title="Recent commands"
              description="Most recent remote activity across the visible operational scope."
              aside={<Link className="secondary-button" href="/commands">Open commands</Link>}
            >
              {snapshot?.recentCommands.length ? (
                <table className="hes-data-table">
                  <thead>
                    <tr>
                      <th>Meter</th>
                      <th>Command</th>
                      <th>Status</th>
                      <th>Outcome</th>
                      <th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snapshot.recentCommands.map((command) => (
                      <tr key={command.command_id}>
                        <td>{command.meter_id}</td>
                        <td>
                          <strong>{command.command_template_code}</strong>
                        </td>
                        <td>
                          <StatusChip
                            label={formatStatusLabel(command.command_status)}
                            tone={getStatusTone(command.command_status)}
                          />
                        </td>
                        <td>{formatFamilySummary(command.family_specific_outcome_summary)}</td>
                        <td>{formatDateTime(command.latest_updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="hes-empty-copy">No recent command activity.</p>
              )}
            </DataTableShell>

            <SurfaceCard
              title="Priority queue"
              description="Immediate operator actions surfaced from approvals, alarms, connectivity, and reads."
            >
              <div className="hes-queue-list">
                {attentionQueue.length === 0 ? (
                  <p className="muted">No priority work items are currently open.</p>
                ) : (
                  attentionQueue.map((item) => (
                    <article key={item.id} className="hes-queue-item">
                      <div>
                        <strong>{item.label}</strong>
                        <p>{item.summary}</p>
                      </div>
                      <div className="hes-queue-item-actions">
                        <StatusChip label={String(item.count)} tone={item.tone} />
                        <Link className="secondary-button" href={item.href}>
                          {item.action}
                        </Link>
                      </div>
                    </article>
                  ))
                )}
              </div>
            </SurfaceCard>
          </div>

          <div className="hes-two-column-grid">
            <SurfaceCard
              title="Reading activity"
              description="Current read coverage across the visible dashboard scope."
              aside={<Link className="secondary-button" href="/readings">Open readings</Link>}
            >
              {readingSummary ? (
                <SummaryList
                  items={[
                    {
                      label: "Meters with recent reads",
                      value: String(readingSummary.captured),
                      tone: "positive",
                    },
                    {
                      label: "Meters missing reads",
                      value: String(readingSummary.missing),
                      tone: readingSummary.missing > 0 ? "warning" : "neutral",
                    },
                    {
                      label: "Flagged read quality",
                      value: String(readingSummary.flagged),
                      tone: readingSummary.flagged > 0 ? "danger" : "neutral",
                    },
                  ]}
                />
              ) : (
                <p className="muted">Reading activity is not available.</p>
              )}
            </SurfaceCard>

            <SurfaceCard
              title="GIS / network snapshot"
              description="Current mapping posture for meters in the reviewed scope."
              aside={<Link className="secondary-button" href="/gis-lite">Open GIS Lite</Link>}
            >
              {gisSummary ? (
                <SummaryList
                  items={[
                    { label: "Mapped with coordinates", value: String(gisSummary.mapped), tone: "positive" },
                    {
                      label: "Service-point-only",
                      value: String(gisSummary.servicePointOnly),
                      tone: gisSummary.servicePointOnly > 0 ? "warning" : "neutral",
                    },
                    {
                      label: "Unlinked",
                      value: String(gisSummary.unlinked),
                      tone: gisSummary.unlinked > 0 ? "danger" : "neutral",
                    },
                    { label: "Linked accounts", value: String(gisSummary.linkedAccounts), tone: "info" },
                  ]}
                />
              ) : (
                <p className="muted">GIS context is not available.</p>
              )}
            </SurfaceCard>
          </div>
        </div>

        <div className="hes-dashboard-side">
          <SurfaceCard
            title="Alarm overview"
            description="Recent alarm feed summarized for control-room review."
            aside={<Link className="secondary-button" href="/jobs-events-alerts">Open monitoring</Link>}
          >
            {alarmSummary ? (
              <>
                <SummaryList
                  items={[
                    {
                      label: "Critical",
                      value: String(alarmSummary.critical),
                      tone: alarmSummary.critical > 0 ? "danger" : "neutral",
                    },
                    {
                      label: "Major",
                      value: String(alarmSummary.major),
                      tone: alarmSummary.major > 0 ? "warning" : "neutral",
                    },
                    {
                      label: "Minor / warning",
                      value: String(alarmSummary.warning),
                      tone: alarmSummary.warning > 0 ? "info" : "neutral",
                    },
                    {
                      label: "Open states",
                      value: String(alarmSummary.open),
                      tone: alarmSummary.open > 0 ? "warning" : "neutral",
                    },
                  ]}
                />
                <div className="hes-queue-list">
                  {snapshot?.recentEvents.slice(0, 4).map((event) => (
                    <article key={event.id} className="hes-queue-item">
                      <div>
                        <strong>{event.event_name ?? event.event_code}</strong>
                        <p>
                          {event.meter_id ?? "Unlinked meter"} · {formatDateTime(event.occurred_at)}
                        </p>
                      </div>
                      <StatusChip
                        label={formatStatusLabel(event.severity)}
                        tone={getStatusTone(event.severity)}
                      />
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <p className="muted">Alarm overview is not available.</p>
            )}
          </SurfaceCard>

          <SurfaceCard
            title="Command center"
            description="Current remote action posture for approvals and recent outcomes."
          >
            {commandSummary ? (
              <SummaryList
                items={[
                  {
                    label: "Pending approvals",
                    value: String(commandSummary.pendingApprovals),
                    tone: commandSummary.pendingApprovals > 0 ? "warning" : "neutral",
                  },
                  {
                    label: "Queued",
                    value: String(commandSummary.queued),
                    tone: commandSummary.queued > 0 ? "warning" : "neutral",
                  },
                  { label: "Succeeded", value: String(commandSummary.succeeded), tone: "positive" },
                  {
                    label: "Failed",
                    value: String(commandSummary.failed),
                    tone: commandSummary.failed > 0 ? "danger" : "neutral",
                  },
                ]}
              />
            ) : (
              <p className="muted">Command center summary is not available.</p>
            )}
          </SurfaceCard>

          <SurfaceCard
            title="Quick access"
            description="Short operator-first launch points into active work surfaces."
          >
            <div className="hes-action-grid">
              <ActionTile
                href="/meters"
                title="Meter registry"
                description="Open the inventory table and continue into meter detail routes."
                meta="Inventory"
              />
              <ActionTile
                href="/commands"
                title="Command queue"
                description="Review remote actions, approvals, and recent outcomes."
                meta="Control"
              />
              <ActionTile
                href="/connectivity"
                title="Connectivity"
                description="Investigate stale sessions, offline meters, and signal health."
                meta="Live"
              />
              <ActionTile
                href="/jobs-events-alerts"
                title="Monitoring"
                description="Triage alarms, jobs, and event-driven operational exceptions."
                meta="Alerts"
              />
            </div>
          </SurfaceCard>
        </div>
      </div>
    </div>
  );
}
