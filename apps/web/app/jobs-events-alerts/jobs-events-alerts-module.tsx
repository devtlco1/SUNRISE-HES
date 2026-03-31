"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type JobRunItem = {
  id: string;
  job_definition_id: string;
  target_meter_id: string | null;
  related_command_id: string | null;
  scheduled_for: string;
  available_at: string;
  claimed_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  status: string;
  latest_error_message: string | null;
  related_command: {
    id: string;
    current_status: string;
    command_template_id: string;
    command_template_code: string;
  } | null;
};

type JobRunListResponse = {
  total: number;
  items: JobRunItem[];
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

type ActivityItem = {
  id: string;
  type: "job_run" | "command" | "event";
  title: string;
  category: string;
  status: string;
  meterId: string | null;
  timestamp: string;
  summary: string;
  targetHref: string | null;
};

type AlertItem = {
  id: string;
  label: string;
  reason: string;
  severity: string;
  timestamp: string;
  targetHref: string | null;
};

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

function formatCommandSummary(item: Record<string, string | null>): string {
  if ("terminal_status_category" in item) {
    return item.terminal_status_category ?? "No terminal status yet";
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
  return "No operational summary yet";
}

function buildJobRunTimestamp(jobRun: JobRunItem): string {
  return (
    jobRun.completed_at ??
    jobRun.started_at ??
    jobRun.claimed_at ??
    jobRun.available_at ??
    jobRun.scheduled_for
  );
}

function sortByTimestampDesc<T extends { timestamp: string }>(items: T[]): T[] {
  return [...items].sort(
    (left, right) =>
      new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime(),
  );
}

export function JobsEventsAlertsModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [jobRuns, setJobRuns] = useState<JobRunItem[] | null>(null);
  const [recentCommands, setRecentCommands] = useState<CommandRecentItem[] | null>(
    null,
  );
  const [recentEvents, setRecentEvents] = useState<RecentEventItem[] | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingActivity, setIsLoadingActivity] = useState(false);

  const loadActivity = useCallback(async () => {
    setIsLoadingActivity(true);
    setPageError(null);

    const [jobRunsResult, commandsResult, eventsResult] = await Promise.allSettled([
      authorizedFetch<JobRunListResponse>("/api/v1/job-runs?limit=8"),
      authorizedFetch<CommandRecentListResponse>("/api/v1/commands/recent?limit=8"),
      authorizedFetch<RecentEventListResponse>("/api/v1/events/recent?limit=8"),
    ]);

    const hasJobRuns = jobRunsResult.status === "fulfilled";
    const hasCommands = commandsResult.status === "fulfilled";
    const hasEvents = eventsResult.status === "fulfilled";

    setJobRuns(hasJobRuns ? jobRunsResult.value.items : null);
    setRecentCommands(hasCommands ? commandsResult.value.items : null);
    setRecentEvents(hasEvents ? eventsResult.value.items : null);

    if (!hasJobRuns && !hasCommands && !hasEvents) {
      const errors = [jobRunsResult, commandsResult, eventsResult]
        .filter((result): result is PromiseRejectedResult => result.status === "rejected")
        .map((result) =>
          result.reason instanceof Error
            ? result.reason.message
            : "Unable to load jobs, events, and alerts activity.",
        );
      setPageError(errors[0] ?? "Unable to load jobs, events, and alerts activity.");
    } else if (!hasJobRuns || !hasCommands || !hasEvents) {
      setPageError("Unable to load complete jobs, events, and alerts context.");
    }

    setIsLoadingActivity(false);
  }, [authorizedFetch]);

  useEffect(() => {
    void loadActivity();
  }, [loadActivity]);

  const activityItems = useMemo(() => {
    const items: ActivityItem[] = [];

    for (const jobRun of jobRuns ?? []) {
      const targetHref = jobRun.target_meter_id
        ? `/meters/${jobRun.target_meter_id}`
        : jobRun.related_command_id
          ? "/commands"
          : null;
      items.push({
        id: jobRun.id,
        type: "job_run",
        title:
          jobRun.related_command?.command_template_code ??
          `Job run ${jobRun.id.slice(0, 8)}`,
        category: "job run",
        status: jobRun.status,
        meterId: jobRun.target_meter_id,
        timestamp: buildJobRunTimestamp(jobRun),
        summary:
          jobRun.latest_error_message ??
          (jobRun.related_command
            ? `Related command ${jobRun.related_command.current_status}`
            : `Scheduled ${formatDateTime(jobRun.scheduled_for)}`),
        targetHref,
      });
    }

    for (const command of recentCommands ?? []) {
      items.push({
        id: command.command_id,
        type: "command",
        title: command.command_template_code,
        category: command.command_family,
        status: command.command_status,
        meterId: command.meter_id,
        timestamp: command.latest_updated_at,
        summary: formatCommandSummary(command.family_specific_outcome_summary),
        targetHref: `/meters/${command.meter_id}`,
      });
    }

    for (const event of recentEvents ?? []) {
      items.push({
        id: event.id,
        type: "event",
        title: event.event_name ?? event.event_code,
        category: event.event_code,
        status: `${event.severity} / ${event.event_state}`,
        meterId: event.meter_id,
        timestamp: event.occurred_at,
        summary: `Received ${formatDateTime(event.received_at)}`,
        targetHref: event.meter_id ? `/meters/${event.meter_id}` : null,
      });
    }

    return sortByTimestampDesc(items).slice(0, 12);
  }, [jobRuns, recentCommands, recentEvents]);

  const alertItems = useMemo(() => {
    const alerts: AlertItem[] = [];

    for (const jobRun of jobRuns ?? []) {
      if (!["failed", "timed_out", "cancelled"].includes(jobRun.status)) {
        continue;
      }
      alerts.push({
        id: `job-${jobRun.id}`,
        label:
          jobRun.related_command?.command_template_code ??
          `Job run ${jobRun.id.slice(0, 8)}`,
        reason: jobRun.latest_error_message ?? `Job run ${jobRun.status}`,
        severity: "job",
        timestamp: buildJobRunTimestamp(jobRun),
        targetHref: jobRun.target_meter_id
          ? `/meters/${jobRun.target_meter_id}`
          : jobRun.related_command_id
            ? "/commands"
            : null,
      });
    }

    for (const command of recentCommands ?? []) {
      if (!["failed", "timed_out", "cancelled"].includes(command.command_status)) {
        continue;
      }
      alerts.push({
        id: `command-${command.command_id}`,
        label: command.command_template_code,
        reason: `${command.command_family} ${command.command_status}`,
        severity: "command",
        timestamp: command.latest_updated_at,
        targetHref: `/meters/${command.meter_id}`,
      });
    }

    for (const event of recentEvents ?? []) {
      const isAlertLike =
        event.severity === "critical" ||
        (event.severity === "warning" && event.event_state === "open");
      if (!isAlertLike) {
        continue;
      }
      alerts.push({
        id: `event-${event.id}`,
        label: event.event_name ?? event.event_code,
        reason: `${event.severity} ${event.event_state}`,
        severity: "event",
        timestamp: event.occurred_at,
        targetHref: event.meter_id ? `/meters/${event.meter_id}` : null,
      });
    }

    return sortByTimestampDesc(alerts).slice(0, 5);
  }, [jobRuns, recentCommands, recentEvents]);

  const overviewCards = useMemo(
    () => [
      {
        label: "Recent job runs loaded",
        value: jobRuns ? String(jobRuns.length) : "Not available",
      },
      {
        label: "Recent commands loaded",
        value: recentCommands ? String(recentCommands.length) : "Not available",
      },
      {
        label: "Recent events loaded",
        value: recentEvents ? String(recentEvents.length) : "Not available",
      },
      {
        label: "Derived alerts in current view",
        value: String(alertItems.length),
      },
    ],
    [alertItems.length, jobRuns, recentCommands, recentEvents],
  );

  const activityStatus = useMemo(() => {
    if (isLoadingActivity) {
      return "Loading activity";
    }
    if (pageError && (jobRuns !== null || recentCommands !== null || recentEvents !== null)) {
      return "Partial context";
    }
    return "Activity ready";
  }, [isLoadingActivity, jobRuns, pageError, recentCommands, recentEvents]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Monitoring overview</h2>
              <p className="muted">
                Bounded operational visibility across the existing job, command,
                and event read surfaces.
              </p>
            </div>
            <span className="artifact-pill">{activityStatus}</span>
          </div>

          {isLoadingActivity ? (
            <p className="muted">Loading jobs, events, and alerts overview...</p>
          ) : (
            <div className="meter-summary-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Derived alerts</h2>
              <p className="muted">
                Compact alert-like signals derived from failed jobs, failed
                commands, and critical or open warning events.
              </p>
            </div>
          </div>

          {isLoadingActivity ? (
            <p className="muted">Loading derived alerts...</p>
          ) : (
            <div className="command-list">
              {alertItems.length === 0 ? (
                <p className="muted">
                  No alert-like operational activity is currently visible.
                </p>
              ) : null}

              {alertItems.map((alert) =>
                alert.targetHref ? (
                  <Link
                    key={alert.id}
                    className="command-list-item"
                    href={alert.targetHref}
                  >
                    <div className="command-list-item-header">
                      <strong>{alert.label}</strong>
                      <span className="status-pill">{alert.severity}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{alert.reason}</span>
                      <span>{formatDateTime(alert.timestamp)}</span>
                    </div>
                  </Link>
                ) : (
                  <div key={alert.id} className="command-list-item">
                    <div className="command-list-item-header">
                      <strong>{alert.label}</strong>
                      <span className="status-pill">{alert.severity}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{alert.reason}</span>
                      <span>{formatDateTime(alert.timestamp)}</span>
                    </div>
                  </div>
                ),
              )}
            </div>
          )}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Recent operational activity</h2>
              <p className="muted">
                One compact merged list of recent jobs, commands, and ingested
                events.
              </p>
            </div>
          </div>

          {isLoadingActivity ? (
            <p className="muted">Loading recent operational activity...</p>
          ) : (
            <div className="command-list">
              {activityItems.length === 0 ? (
                <p className="muted">No recent operational activity available.</p>
              ) : null}

              {activityItems.map((item) =>
                item.targetHref ? (
                  <Link key={item.id} className="command-list-item" href={item.targetHref}>
                    <div className="command-list-item-header">
                      <strong>{item.title}</strong>
                      <span className="status-pill">{item.status}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>
                        {item.type} / {item.category}
                      </span>
                      <span>{item.meterId ? `Meter ${item.meterId}` : "No meter target"}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{item.summary}</span>
                      <span>Updated {formatDateTime(item.timestamp)}</span>
                    </div>
                  </Link>
                ) : (
                  <div key={item.id} className="command-list-item">
                    <div className="command-list-item-header">
                      <strong>{item.title}</strong>
                      <span className="status-pill">{item.status}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>
                        {item.type} / {item.category}
                      </span>
                      <span>{item.meterId ? `Meter ${item.meterId}` : "No meter target"}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{item.summary}</span>
                      <span>Updated {formatDateTime(item.timestamp)}</span>
                    </div>
                  </div>
                ),
              )}
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
