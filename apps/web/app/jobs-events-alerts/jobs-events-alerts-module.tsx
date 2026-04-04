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

type JobDefinitionItem = {
  id: string;
  code: string;
  name: string;
  category: string;
  target_type: string;
  schedule_type: string;
  run_at: string | null;
  cron_expression: string | null;
  interval_seconds: number | null;
  command_template_id: string | null;
  default_payload: Record<string, unknown> | null;
  priority: string;
  timeout_seconds: number;
  max_retries: number;
  is_active: boolean;
  notes: string | null;
};

type JobDefinitionListResponse = {
  total: number;
  items: JobDefinitionItem[];
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

function formatDurationFromMs(durationMs: number): string {
  const clampedDurationMs = Math.max(durationMs, 0);
  const totalMinutes = Math.floor(clampedDurationMs / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours > 0 && minutes > 0) {
    return `${hours} hr ${minutes} min`;
  }
  if (hours > 0) {
    return `${hours} hr`;
  }
  if (minutes > 0) {
    return `${minutes} min`;
  }
  return `${Math.max(Math.round(clampedDurationMs / 1000), 1)} sec`;
}

function buildJobRunDurationLabel(jobRun: JobRunItem): string {
  if (!jobRun.started_at || !jobRun.completed_at) {
    return "Not completed";
  }

  const startedAt = new Date(jobRun.started_at);
  const completedAt = new Date(jobRun.completed_at);
  if (Number.isNaN(startedAt.getTime()) || Number.isNaN(completedAt.getTime())) {
    return "Not available";
  }

  return formatDurationFromMs(completedAt.getTime() - startedAt.getTime());
}

function buildJobRunTimingSummary(jobRun: JobRunItem): string {
  if (jobRun.completed_at) {
    return `Completed ${formatDateTime(jobRun.completed_at)}`;
  }
  if (jobRun.started_at) {
    return `Started ${formatDateTime(jobRun.started_at)}`;
  }
  if (jobRun.claimed_at) {
    return `Claimed ${formatDateTime(jobRun.claimed_at)}`;
  }
  return `Scheduled ${formatDateTime(jobRun.scheduled_for)}`;
}

function buildJobRunFailureTimestamp(jobRun: JobRunItem): string {
  return jobRun.cancelled_at ?? jobRun.completed_at ?? jobRun.started_at ?? jobRun.available_at;
}

function buildJobRunFailureSummary(jobRun: JobRunItem): string {
  if (jobRun.cancelled_at) {
    return `Cancelled ${formatDateTime(jobRun.cancelled_at)}`;
  }
  if (jobRun.completed_at) {
    return `Failed ${formatDateTime(jobRun.completed_at)}`;
  }
  if (jobRun.started_at) {
    return `Started ${formatDateTime(jobRun.started_at)}`;
  }
  return `Available ${formatDateTime(jobRun.available_at)}`;
}

function buildJobRunOutcomeSummary(jobRun: JobRunItem): string {
  if (jobRun.latest_error_message) {
    return jobRun.latest_error_message;
  }
  if (jobRun.latest_error_code) {
    return jobRun.latest_error_code;
  }
  if (jobRun.related_command) {
    return `Related command ${formatStatusLabel(jobRun.related_command.current_status)}`;
  }
  if (jobRun.result_summary) {
    const summaryEntries = Object.entries(jobRun.result_summary)
      .filter(([, value]) => value !== null && value !== undefined)
      .slice(0, 2)
      .map(([key, value]) => `${formatStatusLabel(key)} ${String(value)}`);
    if (summaryEntries.length > 0) {
      return summaryEntries.join(" • ");
    }
  }
  return "No execution outcome summary recorded";
}

function formatCalendarDateLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function formatIntervalLabel(intervalSeconds: number | null): string {
  if (!intervalSeconds || intervalSeconds <= 0) {
    return "Interval not configured";
  }
  if (intervalSeconds % 3600 === 0) {
    const hours = intervalSeconds / 3600;
    return `Every ${hours} hour${hours === 1 ? "" : "s"}`;
  }
  if (intervalSeconds % 60 === 0) {
    const minutes = intervalSeconds / 60;
    return `Every ${minutes} min`;
  }
  return `Every ${intervalSeconds} sec`;
}

function buildScheduleSummary(jobDefinition: JobDefinitionItem): string {
  if (jobDefinition.schedule_type === "once") {
    return jobDefinition.run_at
      ? `Runs ${formatDateTime(jobDefinition.run_at)}`
      : "One-time schedule without a recorded run time";
  }
  if (jobDefinition.schedule_type === "interval") {
    return formatIntervalLabel(jobDefinition.interval_seconds);
  }
  if (jobDefinition.schedule_type === "cron") {
    return jobDefinition.cron_expression
      ? `Cron ${jobDefinition.cron_expression}`
      : "Cron schedule not configured";
  }
  return "Manual trigger only";
}

function buildPlanningPosture(jobDefinition: JobDefinitionItem): string {
  return jobDefinition.is_active ? "Active schedule" : "Paused schedule";
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

function buildRetryQueueActivityDetailHref(
  activityType: "job_run" | "command",
  activityId: string,
): string {
  const searchParams = new URLSearchParams({
    retryEntrySource: "jobs_retry_queue",
  });
  return `${buildActivityDetailHref(activityType, activityId)}?${searchParams.toString()}`;
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
  const [jobDefinitions, setJobDefinitions] = useState<JobDefinitionItem[] | null>(null);
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

    const [jobRunsResult, jobDefinitionsResult, commandsResult, eventsResult] =
      await Promise.allSettled([
      authorizedFetch<JobRunListResponse>("/api/v1/job-runs?limit=8"),
      authorizedFetch<JobDefinitionListResponse>("/api/v1/job-definitions"),
      authorizedFetch<CommandRecentListResponse>("/api/v1/commands/recent?limit=8"),
      authorizedFetch<RecentEventListResponse>("/api/v1/events/recent?limit=8"),
      ]);

    const hasJobRuns = jobRunsResult.status === "fulfilled";
    const hasJobDefinitions = jobDefinitionsResult.status === "fulfilled";
    const hasCommands = commandsResult.status === "fulfilled";
    const hasEvents = eventsResult.status === "fulfilled";

    setJobRuns(hasJobRuns ? jobRunsResult.value.items : null);
    setJobDefinitions(hasJobDefinitions ? jobDefinitionsResult.value.items : null);
    setRecentCommands(hasCommands ? commandsResult.value.items : null);
    setRecentEvents(hasEvents ? eventsResult.value.items : null);

    if (!hasJobRuns && !hasJobDefinitions && !hasCommands && !hasEvents) {
      const errors = [jobRunsResult, jobDefinitionsResult, commandsResult, eventsResult]
        .filter((result): result is PromiseRejectedResult => result.status === "rejected")
        .map((result) =>
          result.reason instanceof Error
            ? result.reason.message
            : "Unable to load jobs, events, alerts, and scheduling activity.",
        );
      setPageError(errors[0] ?? "Unable to load jobs, events, alerts, and scheduling activity.");
    } else if (!hasJobRuns || !hasJobDefinitions || !hasCommands || !hasEvents) {
      setPageError("Unable to load complete jobs, events, alerts, and scheduling context.");
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
        detailHref: buildRetryQueueActivityDetailHref("job_run", jobRun.id),
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
        detailHref: buildRetryQueueActivityDetailHref("command", command.command_id),
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
  const completedJobRuns = useMemo(
    () => (jobRuns ?? []).filter((jobRun) => jobRun.completed_at !== null).length,
    [jobRuns],
  );
  const failedJobRuns = useMemo(
    () => (jobRuns ?? []).filter((jobRun) => isRetryWorthyStatus(jobRun.status)).length,
    [jobRuns],
  );
  const runningJobRuns = useMemo(
    () =>
      (jobRuns ?? []).filter((jobRun) =>
        ["running", "claimed", "pending"].includes(jobRun.status),
      ).length,
    [jobRuns],
  );
  const failedJobRunItems = useMemo(
    () =>
      [...(jobRuns ?? [])]
        .filter((jobRun) => isRetryWorthyStatus(jobRun.status))
        .sort(
          (left, right) =>
            new Date(buildJobRunFailureTimestamp(right)).getTime() -
            new Date(buildJobRunFailureTimestamp(left)).getTime(),
        ),
    [jobRuns],
  );
  const retryableFailedJobRuns = useMemo(
    () =>
      failedJobRunItems.filter((jobRun) => jobRun.retry_count < jobRun.max_retries).length,
    [failedJobRunItems],
  );
  const exhaustedFailedJobRuns = useMemo(
    () =>
      failedJobRunItems.filter((jobRun) => jobRun.retry_count >= jobRun.max_retries).length,
    [failedJobRunItems],
  );
  const latestFailedJobRun = failedJobRunItems[0] ?? null;
  const activeScheduledDefinitions = useMemo(
    () => (jobDefinitions ?? []).filter((definition) => definition.is_active).length,
    [jobDefinitions],
  );
  const onceScheduledDefinitions = useMemo(
    () =>
      (jobDefinitions ?? []).filter(
        (definition) => definition.schedule_type === "once" && definition.run_at,
      ),
    [jobDefinitions],
  );
  const recurringScheduledDefinitions = useMemo(
    () =>
      (jobDefinitions ?? []).filter(
        (definition) => definition.schedule_type === "cron" || definition.schedule_type === "interval",
      ),
    [jobDefinitions],
  );
  const manualScheduledDefinitions = useMemo(
    () => (jobDefinitions ?? []).filter((definition) => definition.schedule_type === "manual"),
    [jobDefinitions],
  );
  const schedulerCalendarGroups = useMemo(() => {
    const groups = new Map<
      string,
      { label: string; items: JobDefinitionItem[] }
    >();

    for (const definition of onceScheduledDefinitions) {
      if (!definition.run_at) {
        continue;
      }
      const key = definition.run_at.slice(0, 10);
      const existing = groups.get(key);
      if (existing) {
        existing.items.push(definition);
        continue;
      }
      groups.set(key, {
        label: formatCalendarDateLabel(definition.run_at),
        items: [definition],
      });
    }

    return [...groups.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([, value]) => ({
        ...value,
        items: value.items.sort((left, right) =>
          (left.run_at ?? "").localeCompare(right.run_at ?? ""),
        ),
      }));
  }, [onceScheduledDefinitions]);
  const latestRunByDefinitionId = useMemo(() => {
    const entries = new Map<string, JobRunItem>();
    for (const jobRun of jobRuns ?? []) {
      const existing = entries.get(jobRun.job_definition_id);
      if (!existing) {
        entries.set(jobRun.job_definition_id, jobRun);
        continue;
      }
      if (
        new Date(buildJobRunTimestamp(jobRun)).getTime() >
        new Date(buildJobRunTimestamp(existing)).getTime()
      ) {
        entries.set(jobRun.job_definition_id, jobRun);
      }
    }
    return entries;
  }, [jobRuns]);

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
      {
        label: "Scheduler definitions loaded",
        value: jobDefinitions ? String(jobDefinitions.length) : "Not available",
      },
    ],
    [
      alertItems.length,
      jobDefinitions,
      jobRuns,
      recentCommands,
      recentEvents,
      retryQueueItems.length,
    ],
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
  const selectedJobRun = useMemo(
    () =>
      selectedActivity?.type === "job_run"
        ? (jobRuns ?? []).find((jobRun) => jobRun.id === selectedActivity.id) ?? null
        : null,
    [jobRuns, selectedActivity],
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
              <h2>Scheduler calendar workspace</h2>
              <p className="muted">
                Calendar-like planning view over the current job definition schedules using the
                existing jobs read model.
              </p>
            </div>
            <span className="artifact-pill">
              {(jobDefinitions ?? []).length} definition
              {(jobDefinitions ?? []).length === 1 ? "" : "s"}
            </span>
          </div>

          {isLoadingActivity ? (
            <p className="muted">Loading scheduler calendar workspace...</p>
          ) : (
            <div className="detail-stack">
              <div className="jobs-overview-grid">
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Loaded schedules</span>
                  <strong>{String((jobDefinitions ?? []).length)}</strong>
                </div>
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Active schedules</span>
                  <strong>{String(activeScheduledDefinitions)}</strong>
                </div>
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">One-time calendar anchors</span>
                  <strong>{String(onceScheduledDefinitions.length)}</strong>
                </div>
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Recurring schedules</span>
                  <strong>{String(recurringScheduledDefinitions.length)}</strong>
                </div>
              </div>

              {jobDefinitions?.length === 0 ? (
                <p className="muted">No job schedules are currently visible.</p>
              ) : null}

              {schedulerCalendarGroups.length > 0 ? (
                <section className="detail-stack">
                  <div className="section-heading">
                    <div>
                      <h3>Calendar anchors</h3>
                      <p className="muted">
                        One-time schedules grouped by their configured calendar day.
                      </p>
                    </div>
                  </div>

                  {schedulerCalendarGroups.map((group) => (
                    <div key={group.label} className="command-list-item">
                      <div className="command-list-item-header">
                        <strong>{group.label}</strong>
                        <span className="artifact-pill">
                          {group.items.length} item{group.items.length === 1 ? "" : "s"}
                        </span>
                      </div>

                      <div className="detail-stack">
                        {group.items.map((definition) => {
                          const latestRun = latestRunByDefinitionId.get(definition.id) ?? null;
                          return (
                            <article key={definition.id} className="command-list-item">
                              <div className="command-list-item-header">
                                <strong>{definition.name}</strong>
                                <span
                                  className={`status-pill ${
                                    definition.is_active ? "positive" : "neutral"
                                  }`}
                                >
                                  {buildPlanningPosture(definition)}
                                </span>
                              </div>
                              <div className="command-list-item-badges">
                                <span className="artifact-pill">
                                  {formatStatusLabel(definition.category)}
                                </span>
                                <span className="artifact-pill">
                                  {formatStatusLabel(definition.target_type)}
                                </span>
                                <span className="artifact-pill">
                                  {formatStatusLabel(definition.schedule_type)}
                                </span>
                              </div>
                              <div className="command-list-item-meta">
                                <span>{buildScheduleSummary(definition)}</span>
                                <span>{definition.code}</span>
                              </div>
                              <div className="command-list-item-meta">
                                <span>
                                  {latestRun
                                    ? `Latest run ${formatStatusLabel(latestRun.status)}`
                                    : "No recent run in the current bounded projection."}
                                </span>
                                <span>
                                  {latestRun
                                    ? formatDateTime(buildJobRunTimestamp(latestRun))
                                    : `Timeout ${definition.timeout_seconds} sec`}
                                </span>
                              </div>
                              <div className="artifact-row">
                                {latestRun ? (
                                  <Link
                                    className="secondary-button"
                                    href={buildActivityDetailHref("job_run", latestRun.id)}
                                  >
                                    Open latest run detail
                                  </Link>
                                ) : null}
                              </div>
                            </article>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </section>
              ) : null}

              <div className="jobs-activity-layout">
                <section className="subpanel">
                  <div className="section-heading">
                    <div>
                      <h3>Recurring cadence lane</h3>
                      <p className="muted">
                        Active recurring schedules shown with cadence and latest run context.
                      </p>
                    </div>
                  </div>

                  <div className="command-list">
                    {recurringScheduledDefinitions.length === 0 ? (
                      <p className="muted">No recurring schedules are currently visible.</p>
                    ) : null}

                    {recurringScheduledDefinitions.map((definition) => {
                      const latestRun = latestRunByDefinitionId.get(definition.id) ?? null;
                      return (
                        <article key={definition.id} className="command-list-item">
                          <div className="command-list-item-header">
                            <strong>{definition.name}</strong>
                            <span
                              className={`status-pill ${
                                definition.is_active ? "positive" : "neutral"
                              }`}
                            >
                              {buildPlanningPosture(definition)}
                            </span>
                          </div>
                          <div className="command-list-item-badges">
                            <span className="artifact-pill">
                              {formatStatusLabel(definition.schedule_type)}
                            </span>
                            <span className="artifact-pill">
                              {formatStatusLabel(definition.category)}
                            </span>
                          </div>
                          <div className="command-list-item-meta">
                            <span>{buildScheduleSummary(definition)}</span>
                            <span>{definition.code}</span>
                          </div>
                          <div className="command-list-item-meta">
                            <span>
                              {latestRun
                                ? `Latest run ${formatStatusLabel(latestRun.status)}`
                                : "No recent run in the current bounded projection."}
                            </span>
                            <span>
                              {latestRun
                                ? formatDateTime(buildJobRunTimestamp(latestRun))
                                : `Retry budget ${definition.max_retries}`}
                            </span>
                          </div>
                          <div className="artifact-row">
                            {latestRun ? (
                              <Link
                                className="secondary-button"
                                href={buildActivityDetailHref("job_run", latestRun.id)}
                              >
                                Open latest run detail
                              </Link>
                            ) : null}
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </section>

                <section className="subpanel">
                  <div className="section-heading">
                    <div>
                      <h3>Manual planning lane</h3>
                      <p className="muted">
                        Manual jobs remain visible here as planning anchors without synthetic
                        calendar placement.
                      </p>
                    </div>
                  </div>

                  <div className="command-list">
                    {manualScheduledDefinitions.length === 0 ? (
                      <p className="muted">No manual-only job definitions are currently visible.</p>
                    ) : null}

                    {manualScheduledDefinitions.map((definition) => {
                      const latestRun = latestRunByDefinitionId.get(definition.id) ?? null;
                      return (
                        <article key={definition.id} className="command-list-item">
                          <div className="command-list-item-header">
                            <strong>{definition.name}</strong>
                            <span
                              className={`status-pill ${
                                definition.is_active ? "warning" : "neutral"
                              }`}
                            >
                              {buildPlanningPosture(definition)}
                            </span>
                          </div>
                          <div className="command-list-item-badges">
                            <span className="artifact-pill">Manual</span>
                            <span className="artifact-pill">
                              {formatStatusLabel(definition.category)}
                            </span>
                          </div>
                          <div className="command-list-item-meta">
                            <span>{definition.code}</span>
                            <span>{definition.notes ?? "No planning notes recorded."}</span>
                          </div>
                          <div className="command-list-item-meta">
                            <span>
                              {latestRun
                                ? `Latest run ${formatStatusLabel(latestRun.status)}`
                                : "No recent run in the current bounded projection."}
                            </span>
                            <span>
                              {latestRun
                                ? formatDateTime(buildJobRunTimestamp(latestRun))
                                : `Timeout ${definition.timeout_seconds} sec`}
                            </span>
                          </div>
                          <div className="artifact-row">
                            {latestRun ? (
                              <Link
                                className="secondary-button"
                                href={buildActivityDetailHref("job_run", latestRun.id)}
                              >
                                Open latest run detail
                              </Link>
                            ) : null}
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </section>
              </div>
            </div>
          )}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Failed runs workspace</h2>
              <p className="muted">
                Troubleshooting view for failed, timed-out, and cancelled job runs using the
                current execution and retry context already loaded into this workspace.
              </p>
            </div>
            <span className="artifact-pill">
              {failedJobRunItems.length} failed run{failedJobRunItems.length === 1 ? "" : "s"}
            </span>
          </div>

          {isLoadingActivity ? (
            <p className="muted">Loading failed runs workspace...</p>
          ) : (
            <div className="detail-stack">
              <div className="jobs-overview-grid">
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Visible failed runs</span>
                  <strong>{String(failedJobRunItems.length)}</strong>
                </div>
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Retryable failed runs</span>
                  <strong>{String(retryableFailedJobRuns)}</strong>
                </div>
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Retry budget exhausted</span>
                  <strong>{String(exhaustedFailedJobRuns)}</strong>
                </div>
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Latest failed transition</span>
                  <strong>
                    {formatDateTime(
                      latestFailedJobRun ? buildJobRunFailureTimestamp(latestFailedJobRun) : null,
                    )}
                  </strong>
                </div>
              </div>

              <p className="muted">
                Review the latest failure state, retry posture, and recorded outcome before
                drilling into the existing activity detail or remediation paths.
              </p>

              <div className="command-list">
                {failedJobRunItems.length === 0 ? (
                  <p className="muted">No failed job runs are currently visible.</p>
                ) : null}

                {failedJobRunItems.map((jobRun) => (
                  <article key={jobRun.id} className="command-list-item">
                    <div className="command-list-item-header">
                      <strong>
                        {jobRun.related_command?.command_template_code ??
                          `Job run ${jobRun.id.slice(0, 8)}`}
                      </strong>
                      <span className={`status-pill ${buildStatusTone(jobRun.status)}`}>
                        {formatStatusLabel(jobRun.status)}
                      </span>
                    </div>
                    <div className="command-list-item-badges">
                      <span className="artifact-pill">Job run</span>
                      <span className="artifact-pill">
                        {jobRun.latest_error_code ?? "No error code"}
                      </span>
                      <span className="artifact-pill">
                        {jobRun.worker_identifier ?? "No worker claim"}
                      </span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{buildJobRunFailureSummary(jobRun)}</span>
                      <span>Duration {buildJobRunDurationLabel(jobRun)}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{buildJobRunOutcomeSummary(jobRun)}</span>
                      <span>{formatRetrySummary(jobRun.retry_count, jobRun.max_retries)}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>
                        Retries {jobRun.retry_count}/{jobRun.max_retries}
                      </span>
                      <span>{jobRun.correlation_id ?? "No correlation ID"}</span>
                    </div>
                    <div className="artifact-row">
                      <button
                        className="secondary-button"
                        onClick={() => setSelectedActivityId(jobRun.id)}
                        type="button"
                      >
                        Inspect failed run
                      </button>
                      <Link
                        className="secondary-button"
                        href={buildActivityDetailHref("job_run", jobRun.id)}
                      >
                        Open job run detail
                      </Link>
                      <Link
                        className="secondary-button"
                        href={buildRetryQueueActivityDetailHref("job_run", jobRun.id)}
                      >
                        Open retry detail
                      </Link>
                      {jobRun.related_command_id ? (
                        <Link className="secondary-button" href="/commands">
                          Open commands page
                        </Link>
                      ) : null}
                      {jobRun.target_meter_id ? (
                        <Link
                          className="secondary-button"
                          href={`/meters/${jobRun.target_meter_id}`}
                        >
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
              <h2>Job runs workspace</h2>
              <p className="muted">
                Recent job execution visibility with status, timing, retry, and outcome
                context using the current jobs read model.
              </p>
            </div>
            <span className="artifact-pill">
              {(jobRuns ?? []).length} run{(jobRuns ?? []).length === 1 ? "" : "s"}
            </span>
          </div>

          {isLoadingActivity ? (
            <p className="muted">Loading job runs workspace...</p>
          ) : (
            <div className="detail-stack">
              <div className="jobs-overview-grid">
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Loaded job runs</span>
                  <strong>{String((jobRuns ?? []).length)}</strong>
                </div>
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Completed runs</span>
                  <strong>{String(completedJobRuns)}</strong>
                </div>
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Running or queued</span>
                  <strong>{String(runningJobRuns)}</strong>
                </div>
                <div className="stat-card jobs-overview-card">
                  <span className="stat-label">Failed or timed out</span>
                  <strong>{String(failedJobRuns)}</strong>
                </div>
              </div>

              <div className="command-list">
                {(jobRuns ?? []).length === 0 ? (
                  <p className="muted">No recent job runs are currently visible.</p>
                ) : null}

                {(jobRuns ?? []).map((jobRun) => (
                  <article key={jobRun.id} className="command-list-item">
                    <div className="command-list-item-header">
                      <strong>
                        {jobRun.related_command?.command_template_code ??
                          `Job run ${jobRun.id.slice(0, 8)}`}
                      </strong>
                      <span className={`status-pill ${buildStatusTone(jobRun.status)}`}>
                        {formatStatusLabel(jobRun.status)}
                      </span>
                    </div>
                    <div className="command-list-item-badges">
                      <span className="artifact-pill">Job run</span>
                      <span className="artifact-pill">
                        {jobRun.worker_identifier ?? "No worker claim"}
                      </span>
                      <span className="artifact-pill">
                        {jobRun.correlation_id ?? "No correlation ID"}
                      </span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{buildJobRunTimingSummary(jobRun)}</span>
                      <span>Duration {buildJobRunDurationLabel(jobRun)}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{buildJobRunOutcomeSummary(jobRun)}</span>
                      <span>
                        Retries {jobRun.retry_count}/{jobRun.max_retries}
                      </span>
                    </div>
                    <div className="artifact-row">
                      <Link
                        className="secondary-button"
                        href={buildActivityDetailHref("job_run", jobRun.id)}
                      >
                        Open job run detail
                      </Link>
                      {jobRun.target_meter_id ? (
                        <Link
                          className="secondary-button"
                          href={`/meters/${jobRun.target_meter_id}`}
                        >
                          Open meter detail
                        </Link>
                      ) : null}
                      {jobRun.related_command_id ? (
                        <Link className="secondary-button" href="/commands">
                          Open commands page
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
                {selectedJobRun ? (
                  <>
                    <div className="stat-card">
                      <span className="stat-label">Failure code</span>
                      <strong>{selectedJobRun.latest_error_code ?? "Not available"}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Worker</span>
                      <strong>{selectedJobRun.worker_identifier ?? "Not available"}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Correlation ID</span>
                      <strong>{selectedJobRun.correlation_id ?? "Not available"}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Started</span>
                      <strong>{formatDateTime(selectedJobRun.started_at)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Completed</span>
                      <strong>{formatDateTime(selectedJobRun.completed_at)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Duration</span>
                      <strong>{buildJobRunDurationLabel(selectedJobRun)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Retry posture</span>
                      <strong>{formatRetrySummary(selectedJobRun.retry_count, selectedJobRun.max_retries)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Outcome</span>
                      <strong>{buildJobRunOutcomeSummary(selectedJobRun)}</strong>
                    </div>
                  </>
                ) : null}
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
