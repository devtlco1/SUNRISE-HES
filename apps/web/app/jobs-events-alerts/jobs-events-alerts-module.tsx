"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";
import {
  buildActivityDetailHref,
  formatCommandSummary,
  formatDateTime,
  type ActivityType,
} from "./activity-support";

type JobRunItem = {
  id: string;
  job_definition_id: string;
  target_meter_id: string | null;
  target_endpoint_id: string | null;
  related_command_id: string | null;
  scheduled_for: string;
  available_at: string;
  claimed_at: string | null;
  claim_expires_at: string | null;
  worker_identifier: string | null;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  status: string;
  retry_count: number;
  max_retries: number;
  request_payload: Record<string, unknown> | null;
  result_summary: Record<string, unknown> | null;
  latest_error_code: string | null;
  latest_error_message: string | null;
  correlation_id: string | null;
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
  latest_command_execution_attempt_status: string | null;
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
  type: ActivityType;
  title: string;
  category: string;
  status: string;
  isAttentionItem: boolean;
  meterId: string | null;
  timestamp: string;
  summary: string;
  detailHref: string;
  relatedHref: string | null;
  relatedLabel: string | null;
};

type AlertItem = {
  id: string;
  label: string;
  reason: string;
  severity: string;
  timestamp: string;
  status: string;
  targetHref: string | null;
};

type RetryQueueItem = {
  id: string;
  sourceType: "job_run" | "command";
  title: string;
  category: string;
  status: string;
  timestamp: string;
  meterId: string | null;
  reason: string;
  attemptSummary: string;
  retrySummary: string;
  detailHref: string;
  remediationHref: string | null;
  meterHref: string | null;
  commandsHref: string | null;
};

type AttentionLandingContext = {
  source: "dashboard_attention_queue";
  filter: "attention";
};

type RetryQueueRoundTripContext = {
  source: "activity_detail_roundtrip";
  activityType: "job_run" | "command";
  activityId: string;
};

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

function formatStatusLabel(value: string): string {
  return value
    .split(/[_\s/]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildStatusTone(value: string | null): "positive" | "warning" | "danger" | "neutral" {
  const normalized = value?.toLowerCase() ?? "";
  if (
    normalized.includes("succeed") ||
    normalized.includes("complete") ||
    normalized.includes("closed") ||
    normalized.includes("ready")
  ) {
    return "positive";
  }
  if (
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized.includes("critical") ||
    normalized.includes("cancel") ||
    normalized.includes("open")
  ) {
    return "danger";
  }
  if (
    normalized.includes("warning") ||
    normalized.includes("queued") ||
    normalized.includes("pending") ||
    normalized.includes("running")
  ) {
    return "warning";
  }
  return "neutral";
}

function isRetryWorthyStatus(value: string | null): boolean {
  return ["failed", "timed_out", "cancelled"].includes(value ?? "");
}

function formatRetrySummary(retryCount: number, maxRetries: number): string {
  if (maxRetries <= 0) {
    return "No automatic retry budget configured in the current bounded runtime flow.";
  }

  if (retryCount < maxRetries) {
    const remaining = maxRetries - retryCount;
    return `${remaining} retry slot${remaining === 1 ? "" : "s"} remaining in the current bounded runtime budget.`;
  }

  return "Retry budget exhausted in the current bounded runtime budget.";
}

function buildRetryRemediationHref({
  commandId,
  itemType,
  reason,
  context,
}: {
  commandId: string | null;
  itemType: "job_run" | "command";
  reason: string | null;
  context: string | null;
}): string | null {
  if (!commandId) {
    return null;
  }

  const searchParams = new URLSearchParams({
    selectedCommandId: commandId,
    retrySource: "jobs_retry_queue",
    retryItemType: itemType,
  });

  if (reason) {
    searchParams.set("retryReason", reason);
  }
  if (context) {
    searchParams.set("retryContext", context);
  }

  return `/commands?${searchParams.toString()}`;
}

export function JobsEventsAlertsModule({
  authorizedFetch,
  initialAttentionContext = null,
  initialRetryQueueRoundTripContext = null,
}: {
  authorizedFetch: AuthorizedFetch;
  initialAttentionContext?: AttentionLandingContext | null;
  initialRetryQueueRoundTripContext?: RetryQueueRoundTripContext | null;
}) {
  const [jobRuns, setJobRuns] = useState<JobRunItem[] | null>(null);
  const [recentCommands, setRecentCommands] = useState<CommandRecentItem[] | null>(
    null,
  );
  const [recentEvents, setRecentEvents] = useState<RecentEventItem[] | null>(null);
  const [activityFilter, setActivityFilter] = useState<"all" | "attention">(
    initialAttentionContext?.filter ?? "all",
  );
  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(null);
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
      const relatedHref = jobRun.target_meter_id
        ? `/meters/${jobRun.target_meter_id}`
        : jobRun.related_command_id
          ? "/commands"
          : null;
      const relatedLabel = jobRun.target_meter_id
        ? "Open meter detail"
        : jobRun.related_command_id
          ? "Open commands page"
          : null;
      items.push({
        id: jobRun.id,
        type: "job_run",
        title:
          jobRun.related_command?.command_template_code ??
          `Job run ${jobRun.id.slice(0, 8)}`,
        category: "job run",
        status: jobRun.status,
        isAttentionItem: isRetryWorthyStatus(jobRun.status),
        meterId: jobRun.target_meter_id,
        timestamp: buildJobRunTimestamp(jobRun),
        summary:
          jobRun.latest_error_message ??
          (jobRun.related_command
            ? `Related command ${jobRun.related_command.current_status}`
            : `Scheduled ${formatDateTime(jobRun.scheduled_for)}`),
        detailHref: buildActivityDetailHref("job_run", jobRun.id),
        relatedHref,
        relatedLabel,
      });
    }

    for (const command of recentCommands ?? []) {
      items.push({
        id: command.command_id,
        type: "command",
        title: command.command_template_code,
        category: command.command_family,
        status: command.command_status,
        isAttentionItem: isRetryWorthyStatus(command.command_status),
        meterId: command.meter_id,
        timestamp: command.latest_updated_at,
        summary: formatCommandSummary(command.family_specific_outcome_summary),
        detailHref: buildActivityDetailHref("command", command.command_id),
        relatedHref: `/meters/${command.meter_id}`,
        relatedLabel: "Open meter detail",
      });
    }

    for (const event of recentEvents ?? []) {
      items.push({
        id: event.id,
        type: "event",
        title: event.event_name ?? event.event_code,
        category: event.event_code,
        status: `${event.severity} / ${event.event_state}`,
        isAttentionItem:
          event.severity === "critical" ||
          (event.severity === "warning" && event.event_state === "open"),
        meterId: event.meter_id,
        timestamp: event.occurred_at,
        summary: `Received ${formatDateTime(event.received_at)}`,
        detailHref: buildActivityDetailHref("event", event.id),
        relatedHref: event.meter_id ? `/meters/${event.meter_id}` : null,
        relatedLabel: event.meter_id ? "Open meter detail" : null,
      });
    }

    return sortByTimestampDesc(items).slice(0, 12);
  }, [jobRuns, recentCommands, recentEvents]);
  const filteredActivityItems = useMemo(
    () =>
      activityItems.filter((item) =>
        activityFilter === "attention" ? item.isAttentionItem : true,
      ),
    [activityFilter, activityItems],
  );

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
        status: jobRun.status,
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
        status: command.command_status,
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
        status: `${event.severity} ${event.event_state}`,
        targetHref: event.meter_id ? `/meters/${event.meter_id}` : null,
      });
    }

    return sortByTimestampDesc(alerts).slice(0, 5);
  }, [jobRuns, recentCommands, recentEvents]);
  const retryQueueItems = useMemo(() => {
    const items: RetryQueueItem[] = [];

    for (const jobRun of jobRuns ?? []) {
      if (!isRetryWorthyStatus(jobRun.status)) {
        continue;
      }

      items.push({
        id: `job-run-${jobRun.id}`,
        sourceType: "job_run",
        title:
          jobRun.related_command?.command_template_code ?? `Job run ${jobRun.id.slice(0, 8)}`,
        category: "job run",
        status: jobRun.status,
        timestamp: buildJobRunTimestamp(jobRun),
        meterId: jobRun.target_meter_id,
        reason:
          jobRun.latest_error_message ??
          jobRun.latest_error_code ??
          `Job run ${formatStatusLabel(jobRun.status)}`,
        attemptSummary: `Retries ${jobRun.retry_count}/${jobRun.max_retries}`,
        retrySummary: formatRetrySummary(jobRun.retry_count, jobRun.max_retries),
        detailHref: buildActivityDetailHref("job_run", jobRun.id),
        remediationHref: buildRetryRemediationHref({
          commandId: jobRun.related_command_id,
          itemType: "job_run",
          reason:
            jobRun.latest_error_message ??
            jobRun.latest_error_code ??
            `Job run ${formatStatusLabel(jobRun.status)}`,
          context: `${jobRun.target_meter_id ? `Meter ${jobRun.target_meter_id}. ` : ""}Retries ${jobRun.retry_count}/${jobRun.max_retries}.`,
        }),
        meterHref: jobRun.target_meter_id ? `/meters/${jobRun.target_meter_id}` : null,
        commandsHref: jobRun.related_command_id ? "/commands" : null,
      });
    }

    for (const command of recentCommands ?? []) {
      if (!isRetryWorthyStatus(command.command_status)) {
        continue;
      }

      items.push({
        id: `command-${command.command_id}`,
        sourceType: "command",
        title: command.command_template_code,
        category: command.command_family,
        status: command.command_status,
        timestamp: command.latest_updated_at,
        meterId: command.meter_id,
        reason: formatCommandSummary(command.family_specific_outcome_summary),
        attemptSummary: command.latest_command_execution_attempt_status
          ? `Latest attempt ${formatStatusLabel(command.latest_command_execution_attempt_status)}`
          : "No execution attempt recorded in the current bounded projection.",
        retrySummary: "Retry handoff remains in the stable commands and runtime review flow.",
        detailHref: buildActivityDetailHref("command", command.command_id),
        remediationHref: buildRetryRemediationHref({
          commandId: command.command_id,
          itemType: "command",
          reason: formatCommandSummary(command.family_specific_outcome_summary),
          context: `Meter ${command.meter_id}. ${
            command.latest_command_execution_attempt_status
              ? `Latest attempt ${formatStatusLabel(command.latest_command_execution_attempt_status)}.`
              : "No execution attempt recorded."
          }`,
        }),
        meterHref: `/meters/${command.meter_id}`,
        commandsHref: "/commands",
      });
    }

    return sortByTimestampDesc(items).slice(0, 8);
  }, [jobRuns, recentCommands]);
  const jobRunsWithRetryCapacity = useMemo(
    () =>
      (jobRuns ?? []).filter(
        (jobRun) => isRetryWorthyStatus(jobRun.status) && jobRun.retry_count < jobRun.max_retries,
      ).length,
    [jobRuns],
  );

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
      {
        label: "Retry-worthy execution contexts",
        value: String(retryQueueItems.length),
      },
    ],
    [alertItems.length, jobRuns, recentCommands, recentEvents, retryQueueItems.length],
  );

  useEffect(() => {
    setSelectedActivityId((currentSelectedActivityId) => {
      if (
        currentSelectedActivityId &&
        filteredActivityItems.some((item) => item.id === currentSelectedActivityId)
      ) {
        return currentSelectedActivityId;
      }
      return filteredActivityItems[0]?.id ?? null;
    });
  }, [filteredActivityItems]);

  const selectedActivity = useMemo(
    () =>
      filteredActivityItems.find((item) => item.id === selectedActivityId) ??
      filteredActivityItems[0] ??
      null,
    [filteredActivityItems, selectedActivityId],
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
  const activityFilterSummary = useMemo(() => {
    if (activityFilter === "attention") {
      return "Attention-only landing from the dashboard handoff. Review alert-like jobs, commands, and events first, or switch back to the full activity list.";
    }
    return "All recent jobs, commands, and events visible in the current bounded monitoring scope.";
  }, [activityFilter]);
  const retryQueueRoundTripSummary = useMemo(() => {
    if (!initialRetryQueueRoundTripContext) {
      return null;
    }

    const activityLabel =
      initialRetryQueueRoundTripContext.activityType === "job_run" ? "job run" : "command";
    return `Returned from the ${activityLabel} activity detail after bounded remediation review. The retry queue remains available below for the next follow-up.`;
  }, [initialRetryQueueRoundTripContext]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel jobs-overview-panel">
          <div className="section-heading">
            <div>
              <h2>Operations monitoring center</h2>
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
            <div className="jobs-overview-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card jobs-overview-card">
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
              <h2>Job runs + retry queue</h2>
              <p className="muted">
                Recent retry-worthy job runs and problematic command execution contexts in one
                bounded operational queue.
              </p>
            </div>
            <span className="artifact-pill">
              {retryQueueItems.length} retry item{retryQueueItems.length === 1 ? "" : "s"}
            </span>
          </div>

          {isLoadingActivity ? (
            <p className="muted">Loading job runs and retry queue...</p>
          ) : (
            <div className="detail-stack">
              <div className="jobs-overview-grid">
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Retry-worthy items</span>
                  <strong>{retryQueueItems.length}</strong>
                </div>
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Job runs with retry capacity</span>
                  <strong>{jobRunsWithRetryCapacity}</strong>
                </div>
              </div>

              <p className="muted">
                Scan recent failed, timed-out, or cancelled execution contexts, then drill into the
                existing activity detail, commands flow, or meter context for bounded follow-up.
              </p>

              {initialRetryQueueRoundTripContext ? (
                <div className="detail-stack">
                  <p className="muted">{retryQueueRoundTripSummary}</p>
                  <div className="artifact-row">
                    <span className="artifact-pill">Retry queue round-trip</span>
                    <span className="artifact-pill">
                      {formatStatusLabel(initialRetryQueueRoundTripContext.activityType)}
                    </span>
                    <span className="artifact-pill">
                      {initialRetryQueueRoundTripContext.activityId}
                    </span>
                  </div>
                </div>
              ) : null}

              <div className="command-list">
                {retryQueueItems.length === 0 ? (
                  <p className="muted">
                    No retry-worthy job runs or problematic command execution contexts are
                    currently visible.
                  </p>
                ) : null}

                {retryQueueItems.map((item) => (
                  <article key={item.id} className="command-list-item">
                    <div className="command-list-item-header">
                      <strong>{item.title}</strong>
                      <span className={`status-pill ${buildStatusTone(item.status)}`}>
                        {formatStatusLabel(item.status)}
                      </span>
                    </div>
                    <div className="command-list-item-badges">
                      <span className="artifact-pill">{formatStatusLabel(item.sourceType)}</span>
                      <span className="artifact-pill">{formatStatusLabel(item.category)}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{item.meterId ? `Meter ${item.meterId}` : "No meter target"}</span>
                      <span>{formatDateTime(item.timestamp)}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{item.reason}</span>
                      <span>{item.attemptSummary}</span>
                    </div>
                    <p className="muted">{item.retrySummary}</p>
                    <div className="artifact-row">
                      {item.remediationHref ? (
                        <Link className="primary-button" href={item.remediationHref}>
                          Open remediation context
                        </Link>
                      ) : null}
                      <Link className="secondary-button" href={item.detailHref}>
                        Open retry detail
                      </Link>
                      {item.commandsHref ? (
                        <Link className="secondary-button" href={item.commandsHref}>
                          Open commands page
                        </Link>
                      ) : null}
                      {item.meterHref ? (
                        <Link className="secondary-button" href={item.meterHref}>
                          Open meter detail
                        </Link>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
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

          {initialAttentionContext ? (
            <div className="detail-stack">
              <p className="muted">
                Dashboard attention handoff opened this monitoring surface with attention-oriented
                activity preselected.
              </p>
              <div className="artifact-row">
                <span className="artifact-pill">Dashboard attention handoff</span>
                <span className="artifact-pill">Attention-only landing</span>
              </div>
            </div>
          ) : null}

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
                      <span className={`status-pill ${buildStatusTone(alert.status)}`}>
                        {formatStatusLabel(alert.severity)}
                      </span>
                    </div>
                    <div className="command-list-item-badges">
                      <span className={`status-pill ${buildStatusTone(alert.status)}`}>
                        {formatStatusLabel(alert.status)}
                      </span>
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
                      <span className={`status-pill ${buildStatusTone(alert.status)}`}>
                        {formatStatusLabel(alert.severity)}
                      </span>
                    </div>
                    <div className="command-list-item-badges">
                      <span className={`status-pill ${buildStatusTone(alert.status)}`}>
                        {formatStatusLabel(alert.status)}
                      </span>
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

        <div className="jobs-activity-layout">
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

          <div className="artifact-row">
            <button
              className={activityFilter === "all" ? "primary-button" : "secondary-button"}
              onClick={() => setActivityFilter("all")}
              type="button"
            >
              All activity
            </button>
            <button
              className={activityFilter === "attention" ? "primary-button" : "secondary-button"}
              onClick={() => setActivityFilter("attention")}
              type="button"
            >
              Attention only
            </button>
          </div>

          <p className="muted">{activityFilterSummary}</p>

          {isLoadingActivity ? (
            <p className="muted">Loading recent operational activity...</p>
          ) : (
            <div className="command-list">
              {filteredActivityItems.length === 0 ? (
                <p className="muted">
                  {activityFilter === "attention"
                    ? "No attention-oriented operational activity is currently visible."
                    : "No recent operational activity available."}
                </p>
              ) : null}

              {filteredActivityItems.map((item) => (
                <div key={item.id} className="command-list-item">
                  <div className="command-list-item-header">
                    <strong>{item.title}</strong>
                    <span className={`status-pill ${buildStatusTone(item.status)}`}>
                      {formatStatusLabel(item.status)}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">{formatStatusLabel(item.type)}</span>
                    <span className="artifact-pill">{formatStatusLabel(item.category)}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{item.meterId ? `Meter ${item.meterId}` : "No meter target"}</span>
                    <span>{formatDateTime(item.timestamp)}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{item.summary}</span>
                    <span>Updated {formatDateTime(item.timestamp)}</span>
                  </div>
                  <div className="artifact-row">
                    <button
                      className="secondary-button"
                      onClick={() => setSelectedActivityId(item.id)}
                      type="button"
                    >
                      Inspect summary
                    </button>
                    <Link className="secondary-button" href={item.detailHref}>
                      Open activity detail
                    </Link>
                    {item.relatedHref && item.relatedLabel ? (
                      <Link className="secondary-button" href={item.relatedHref}>
                        {item.relatedLabel}
                      </Link>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Selected activity summary</h2>
              <p className="muted">
                Bounded inline summary for the selected operational item before drilling
                into the existing activity detail route.
              </p>
            </div>
          </div>

          {isLoadingActivity ? (
            <p className="muted">Loading selected activity summary...</p>
          ) : selectedActivity ? (
            <div className="detail-stack">
              <section className="jobs-activity-hero">
                <div className="jobs-activity-hero-row">
                  <div>
                    <p className="eyebrow">Selected Activity</p>
                    <h3>{selectedActivity.title}</h3>
                    <p className="muted">
                      {formatStatusLabel(selectedActivity.type)} activity in the{" "}
                      {formatStatusLabel(selectedActivity.category)} operational lane.
                    </p>
                  </div>
                  <span className={`status-pill ${buildStatusTone(selectedActivity.status)}`}>
                    {formatStatusLabel(selectedActivity.status)}
                  </span>
                </div>

                <div className="command-list-item-badges">
                  <span className="artifact-pill">{formatStatusLabel(selectedActivity.type)}</span>
                  <span className="artifact-pill">
                    {formatStatusLabel(selectedActivity.category)}
                  </span>
                  <span className="artifact-pill">
                    {selectedActivity.meterId
                      ? `Meter ${selectedActivity.meterId}`
                      : "No meter target"}
                  </span>
                </div>
              </section>

              <div className="detail-grid">
                <div className="stat-card">
                  <span className="stat-label">Current status</span>
                  <strong>{formatStatusLabel(selectedActivity.status)}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Activity timestamp</span>
                  <strong>{formatDateTime(selectedActivity.timestamp)}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Related meter</span>
                  <strong>
                    {selectedActivity.meterId ? selectedActivity.meterId : "Not available"}
                  </strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Summary</span>
                  <strong>{selectedActivity.summary}</strong>
                </div>
              </div>

              <div className="artifact-row">
                <Link className="secondary-button" href={selectedActivity.detailHref}>
                  Open activity detail
                </Link>
                {selectedActivity.relatedHref && selectedActivity.relatedLabel ? (
                  <Link className="secondary-button" href={selectedActivity.relatedHref}>
                    {selectedActivity.relatedLabel}
                  </Link>
                ) : null}
              </div>
            </div>
          ) : (
            <p className="muted">No activity selected for bounded summary review.</p>
          )}
        </section>
        </div>
      </div>
    </section>
  );
}
