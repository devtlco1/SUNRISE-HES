"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../../../../operational-shell";
import {
  formatCommandSummary,
  formatDateTime,
  type ActivityType,
} from "../../../activity-support";

type JobRunDetail = {
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
  status: string;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
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

type CommandOperationalDetail = {
  command_id: string;
  command_family: string;
  command_category: string;
  command_status: string;
  meter_id: string;
  command_template_code: string;
  latest_command_execution_attempt_id: string | null;
  latest_command_execution_attempt_status: string | null;
  runtime_execution_record_id: string | null;
  family_specific_outcome_summary: Record<string, string | null>;
  orchestration_artifact_present: boolean;
  terminalization_artifact_present: boolean;
  execute_now_artifact_present: boolean;
  created_at: string;
  latest_updated_at: string;
  projection_record: Record<string, unknown>;
};

type CommandOperationalDetailResponse = {
  result: CommandOperationalDetail;
};

type EventDetail = {
  id: string;
  meter_id: string | null;
  related_batch_id: string | null;
  related_attempt_id: string | null;
  event_code: string;
  event_name: string | null;
  severity: string;
  event_state: string;
  occurred_at: string;
  received_at: string;
  raw_payload: Record<string, unknown> | null;
  normalized_payload: Record<string, unknown> | null;
  correlation_id: string | null;
};

type ActivityDetail =
  | { type: "job_run"; record: JobRunDetail }
  | { type: "command"; record: CommandOperationalDetail }
  | { type: "event"; record: EventDetail };

type ActivityDetailReturnContext = {
  source: "commands_remediation";
} | null;

function isActivityType(value: string): value is ActivityType {
  return value === "job_run" || value === "command" || value === "event";
}

function renderJson(value: Record<string, unknown> | null): string {
  if (!value) {
    return "Not available";
  }
  return JSON.stringify(value, null, 2);
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
    normalized.includes("active")
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

function buildRetryRemediationHref({
  commandId,
  itemType,
  reason,
  context,
  originActivityType,
  originActivityId,
}: {
  commandId: string | null;
  itemType: "job_run" | "command";
  reason: string | null;
  context: string | null;
  originActivityType?: "job_run" | "command";
  originActivityId?: string;
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
  if (originActivityType) {
    searchParams.set("retryOriginActivityType", originActivityType);
  }
  if (originActivityId) {
    searchParams.set("retryOriginActivityId", originActivityId);
  }

  return `/commands?${searchParams.toString()}`;
}

function buildJobsEventsAlertsReturnHref({
  activityType,
  activityId,
  returnContext,
  isRetryWorthyActivity,
}: {
  activityType: ActivityType;
  activityId: string;
  returnContext: ActivityDetailReturnContext;
  isRetryWorthyActivity: boolean;
}): string {
  if (
    returnContext?.source !== "commands_remediation" ||
    !isRetryWorthyActivity ||
    activityType === "event"
  ) {
    return "/jobs-events-alerts";
  }

  const searchParams = new URLSearchParams({
    retryQueueReturnSource: "activity_detail_roundtrip",
    returnedActivityType: activityType,
    returnedActivityId: activityId,
  });
  return `/jobs-events-alerts?${searchParams.toString()}`;
}

export function ActivityDetailModule({
  activityType,
  activityId,
  authorizedFetch,
  initialReturnContext = null,
}: {
  activityType: string;
  activityId: string;
  authorizedFetch: AuthorizedFetch;
  initialReturnContext?: ActivityDetailReturnContext;
}) {
  const [detail, setDetail] = useState<ActivityDetail | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const loadDetail = useCallback(async () => {
    if (!isActivityType(activityType)) {
      setDetail(null);
      setPageError("Unsupported activity type.");
      return;
    }

    setIsLoadingDetail(true);
    setPageError(null);

    try {
      if (activityType === "job_run") {
        const response = await authorizedFetch<JobRunDetail>(
          `/api/v1/job-runs/${activityId}`,
        );
        setDetail({ type: "job_run", record: response });
      } else if (activityType === "command") {
        const response = await authorizedFetch<CommandOperationalDetailResponse>(
          `/api/v1/commands/${activityId}/detail`,
        );
        setDetail({ type: "command", record: response.result });
      } else {
        const response = await authorizedFetch<EventDetail>(`/api/v1/events/${activityId}`);
        setDetail({ type: "event", record: response });
      }
    } catch (error) {
      setDetail(null);
      setPageError(
        error instanceof Error ? error.message : "Unable to load activity detail.",
      );
    } finally {
      setIsLoadingDetail(false);
    }
  }, [activityId, activityType, authorizedFetch]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const relatedLinks = useMemo(() => {
    if (!detail) {
      return [];
    }

    if (detail.type === "job_run") {
      const links: Array<{ href: string; label: string }> = [];
      if (detail.record.target_meter_id) {
        links.push({
          href: `/meters/${detail.record.target_meter_id}`,
          label: "Open meter detail",
        });
      }
      if (detail.record.related_command_id) {
        links.push({ href: "/commands", label: "Open commands page" });
      }
      return links;
    }

    if (detail.type === "command") {
      return [
        { href: `/meters/${detail.record.meter_id}`, label: "Open meter detail" },
        { href: "/commands", label: "Open commands page" },
      ];
    }

    if (!detail.record.meter_id) {
      return [];
    }
    return [
      {
        href: `/meters/${detail.record.meter_id}`,
        label: "Open meter detail",
      },
    ];
  }, [detail]);
  const remediationHref = useMemo(() => {
    if (!detail) {
      return null;
    }

    if (detail.type === "job_run") {
      if (!isRetryWorthyStatus(detail.record.status)) {
        return null;
      }

      return buildRetryRemediationHref({
        commandId: detail.record.related_command_id,
        itemType: "job_run",
        reason:
          detail.record.latest_error_message ??
          detail.record.latest_error_code ??
          `Job run ${formatStatusLabel(detail.record.status)}`,
        context: `${detail.record.target_meter_id ? `Meter ${detail.record.target_meter_id}. ` : ""}Retries ${detail.record.retry_count}/${detail.record.max_retries}.`,
        originActivityType: "job_run",
        originActivityId: detail.record.id,
      });
    }

    if (detail.type === "command") {
      if (!isRetryWorthyStatus(detail.record.command_status)) {
        return null;
      }

      return buildRetryRemediationHref({
        commandId: detail.record.command_id,
        itemType: "command",
        reason: formatCommandSummary(detail.record.family_specific_outcome_summary),
        context: `Meter ${detail.record.meter_id}. ${
          detail.record.latest_command_execution_attempt_status
            ? `Latest attempt ${formatStatusLabel(detail.record.latest_command_execution_attempt_status)}.`
            : "No execution attempt recorded."
        }`,
        originActivityType: "command",
        originActivityId: detail.record.command_id,
      });
    }

    return null;
  }, [detail]);
  const jobsEventsAlertsReturnHref = useMemo(() => {
    if (!detail) {
      return "/jobs-events-alerts";
    }

    const currentStatus =
      detail.type === "job_run"
        ? detail.record.status
        : detail.type === "command"
          ? detail.record.command_status
          : null;

    return buildJobsEventsAlertsReturnHref({
      activityType: detail.type,
      activityId,
      returnContext: initialReturnContext,
      isRetryWorthyActivity: isRetryWorthyStatus(currentStatus),
    });
  }, [activityId, detail, initialReturnContext]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        {initialReturnContext ? (
          <section className="subpanel">
            <div className="detail-stack">
              <p className="muted">
                Returned from the commands remediation context for this retry-worthy activity.
              </p>
              <div className="artifact-row">
                <span className="artifact-pill">Retry-origin return</span>
                <span className="artifact-pill">Commands remediation</span>
              </div>
            </div>
          </section>
        ) : null}

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Activity detail</h2>
              <p className="muted">
                Bounded drill-down for one selected monitoring activity item.
              </p>
            </div>
          </div>

          {isLoadingDetail ? (
            <p className="muted">Loading activity detail...</p>
          ) : null}

          {!isLoadingDetail && !detail && !pageError ? (
            <p className="muted">No activity detail available.</p>
          ) : null}

          {!isLoadingDetail && detail?.type === "job_run" ? (
            <div className="detail-stack">
              <section className="jobs-activity-hero">
                <div className="jobs-activity-hero-row">
                  <div>
                    <p className="eyebrow">Selected Activity</p>
                    <h3>{detail.record.related_command?.command_template_code ?? detail.record.id}</h3>
                    <p className="muted">
                      Job run visibility over the current scheduling and execution summary.
                    </p>
                  </div>
                  <span className={`status-pill ${buildStatusTone(detail.record.status)}`}>
                    {formatStatusLabel(detail.record.status)}
                  </span>
                </div>
              </section>

              <div className="meter-summary-grid">
                <div className="stat-card">
                  <span className="stat-label">Activity type</span>
                  <strong>job_run</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Job run ID</span>
                  <strong>{detail.record.id}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Status</span>
                  <strong>{formatStatusLabel(detail.record.status)}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Job definition</span>
                  <strong>{detail.record.job_definition_id}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Meter ID</span>
                  <strong>{detail.record.target_meter_id ?? "Not available"}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Linked command ID</span>
                  <strong>{detail.record.related_command_id ?? "Not available"}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Scheduled</span>
                  <strong>{formatDateTime(detail.record.scheduled_for)}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Completed</span>
                  <strong>{formatDateTime(detail.record.completed_at)}</strong>
                </div>
              </div>

              <div className="command-list-item">
                <div className="command-list-item-header">
                  <strong>Outcome summary</strong>
                  <span
                    className={`status-pill ${buildStatusTone(
                      detail.record.related_command?.current_status ?? detail.record.status,
                    )}`}
                  >
                    {formatStatusLabel(
                      detail.record.related_command?.current_status ?? detail.record.status,
                    )}
                  </span>
                </div>
                <div className="command-list-item-meta">
                  <span>
                    {detail.record.latest_error_message ??
                      detail.record.latest_error_code ??
                      "No error summary recorded."}
                  </span>
                  <span>
                    Retries {detail.record.retry_count}/{detail.record.max_retries}
                  </span>
                </div>
              </div>
            </div>
          ) : null}

          {!isLoadingDetail && detail?.type === "command" ? (
            <div className="detail-stack">
              <section className="jobs-activity-hero">
                <div className="jobs-activity-hero-row">
                  <div>
                    <p className="eyebrow">Selected Activity</p>
                    <h3>{detail.record.command_template_code}</h3>
                    <p className="muted">
                      Command visibility over the current operational projection and attempt state.
                    </p>
                  </div>
                  <span className={`status-pill ${buildStatusTone(detail.record.command_status)}`}>
                    {formatStatusLabel(detail.record.command_status)}
                  </span>
                </div>
              </section>

              <div className="meter-summary-grid">
                <div className="stat-card">
                  <span className="stat-label">Activity type</span>
                  <strong>command</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Command ID</span>
                  <strong>{detail.record.command_id}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Family</span>
                  <strong>{formatStatusLabel(detail.record.command_family)}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Status</span>
                  <strong>{formatStatusLabel(detail.record.command_status)}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Meter ID</span>
                  <strong>{detail.record.meter_id}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Template</span>
                  <strong>{detail.record.command_template_code}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Created</span>
                  <strong>{formatDateTime(detail.record.created_at)}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Updated</span>
                  <strong>{formatDateTime(detail.record.latest_updated_at)}</strong>
                </div>
              </div>

              <div className="command-list-item">
                <div className="command-list-item-header">
                  <strong>Outcome summary</strong>
                  <span
                    className={`status-pill ${buildStatusTone(
                      detail.record.latest_command_execution_attempt_status,
                    )}`}
                  >
                    {formatStatusLabel(
                      detail.record.latest_command_execution_attempt_status ?? "No attempt",
                    )}
                  </span>
                </div>
                <div className="command-list-item-meta">
                  <span>
                    {formatCommandSummary(detail.record.family_specific_outcome_summary)}
                  </span>
                  <span>
                    Runtime record {detail.record.runtime_execution_record_id ?? "Not recorded"}
                  </span>
                </div>
              </div>
            </div>
          ) : null}

          {!isLoadingDetail && detail?.type === "event" ? (
            <div className="detail-stack">
              <section className="jobs-activity-hero">
                <div className="jobs-activity-hero-row">
                  <div>
                    <p className="eyebrow">Selected Activity</p>
                    <h3>{detail.record.event_name ?? detail.record.event_code}</h3>
                    <p className="muted">
                      Event visibility over the current operational severity, state, and payload context.
                    </p>
                  </div>
                  <span
                    className={`status-pill ${buildStatusTone(
                      `${detail.record.severity} ${detail.record.event_state}`,
                    )}`}
                  >
                    {formatStatusLabel(`${detail.record.severity} ${detail.record.event_state}`)}
                  </span>
                </div>
              </section>

              <div className="meter-summary-grid">
                <div className="stat-card">
                  <span className="stat-label">Activity type</span>
                  <strong>event</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Event ID</span>
                  <strong>{detail.record.id}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Event code</span>
                  <strong>{detail.record.event_code}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Severity / state</span>
                  <strong>
                    {detail.record.severity} / {detail.record.event_state}
                  </strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Meter ID</span>
                  <strong>{detail.record.meter_id ?? "Not available"}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Linked attempt ID</span>
                  <strong>{detail.record.related_attempt_id ?? "Not available"}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Occurred</span>
                  <strong>{formatDateTime(detail.record.occurred_at)}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Received</span>
                  <strong>{formatDateTime(detail.record.received_at)}</strong>
                </div>
              </div>

              <div className="command-list-item">
                <div className="command-list-item-header">
                  <strong>Event summary</strong>
                  <span
                    className={`status-pill ${buildStatusTone(
                      `${detail.record.severity} ${detail.record.event_state}`,
                    )}`}
                  >
                    {detail.record.event_name ?? "No name"}
                  </span>
                </div>
                <div className="command-list-item-meta">
                  <span>Correlation {detail.record.correlation_id ?? "Not available"}</span>
                  <span>Batch {detail.record.related_batch_id ?? "Not available"}</span>
                </div>
              </div>
            </div>
          ) : null}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Related operational surfaces</h2>
              <p className="muted">
                Bounded navigation back into the existing operational pages.
              </p>
            </div>
          </div>

          {isLoadingDetail ? (
            <p className="muted">Loading related operational surfaces...</p>
          ) : (
            <div className="artifact-row">
              <Link className="secondary-button" href={jobsEventsAlertsReturnHref}>
                Back to jobs / events / alerts
              </Link>
              {remediationHref ? (
                <Link className="primary-button" href={remediationHref}>
                  Open remediation context
                </Link>
              ) : null}
              {relatedLinks.map((link) => (
                <Link key={link.href} className="secondary-button" href={link.href}>
                  {link.label}
                </Link>
              ))}
            </div>
          )}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Compact payload view</h2>
              <p className="muted">
                Minimal read-only payload visibility for the selected activity.
              </p>
            </div>
          </div>

          {isLoadingDetail ? (
            <p className="muted">Loading activity payload...</p>
          ) : null}

          {!isLoadingDetail && detail?.type === "job_run" ? (
            <div className="detail-stack">
              <div className="command-list-item">
                <div className="command-list-item-header">
                  <strong>Request payload</strong>
                </div>
                <pre>{renderJson(detail.record.request_payload)}</pre>
              </div>
              <div className="command-list-item">
                <div className="command-list-item-header">
                  <strong>Result summary</strong>
                </div>
                <pre>{renderJson(detail.record.result_summary)}</pre>
              </div>
            </div>
          ) : null}

          {!isLoadingDetail && detail?.type === "command" ? (
            <div className="command-list-item">
              <div className="command-list-item-header">
                <strong>Projection record</strong>
              </div>
              <pre>{renderJson(detail.record.projection_record)}</pre>
            </div>
          ) : null}

          {!isLoadingDetail && detail?.type === "event" ? (
            <div className="detail-stack">
              <div className="command-list-item">
                <div className="command-list-item-header">
                  <strong>Normalized payload</strong>
                </div>
                <pre>{renderJson(detail.record.normalized_payload)}</pre>
              </div>
              <div className="command-list-item">
                <div className="command-list-item-header">
                  <strong>Raw payload</strong>
                </div>
                <pre>{renderJson(detail.record.raw_payload)}</pre>
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </section>
  );
}
