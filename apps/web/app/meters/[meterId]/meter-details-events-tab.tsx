"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../../operational-shell";
import { buildActivityDetailHref, formatDateTime } from "../../jobs-events-alerts/activity-support";

type MeterEventItem = {
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

type MeterEventListResponse = {
  total: number;
  items: MeterEventItem[];
};

function formatLabel(value: string | null): string {
  if (!value) {
    return "Not recorded";
  }

  return value
    .split(/[._/\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildStatusTone(value: string | null): "positive" | "warning" | "danger" | "neutral" {
  const normalized = value?.toLowerCase() ?? "";
  if (
    normalized.includes("closed") ||
    normalized.includes("clear") ||
    normalized.includes("normal") ||
    normalized.includes("info")
  ) {
    return "positive";
  }
  if (
    normalized.includes("critical") ||
    normalized.includes("error") ||
    normalized.includes("open")
  ) {
    return "danger";
  }
  if (
    normalized.includes("warning") ||
    normalized.includes("pending") ||
    normalized.includes("acknowledged")
  ) {
    return "warning";
  }
  return "neutral";
}

function buildEventSummary(item: MeterEventItem): string {
  const payloadEntries = Object.entries(item.normalized_payload ?? item.raw_payload ?? {}).slice(0, 2);
  if (payloadEntries.length > 0) {
    return payloadEntries
      .map(([key, value]) => `${formatLabel(key)} ${String(value)}`)
      .join(" • ");
  }

  if (item.correlation_id) {
    return `Correlation ${item.correlation_id}`;
  }

  if (item.related_attempt_id) {
    return `Attempt ${item.related_attempt_id}`;
  }

  if (item.related_batch_id) {
    return `Batch ${item.related_batch_id}`;
  }

  return `Received ${formatDateTime(item.received_at)}`;
}

export function MeterDetailsEventsTab({
  meterId,
  authorizedFetch,
}: {
  meterId: string;
  authorizedFetch: AuthorizedFetch;
}) {
  const [events, setEvents] = useState<MeterEventItem[]>([]);
  const [totalEvents, setTotalEvents] = useState(0);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);

  const loadEvents = useCallback(async () => {
    setIsLoadingEvents(true);
    setPageError(null);

    try {
      const response = await authorizedFetch<MeterEventListResponse>(
        `/api/v1/meters/${meterId}/ingested-events?limit=12`,
      );
      setEvents(response.items);
      setTotalEvents(response.total);
    } catch (error) {
      setEvents([]);
      setTotalEvents(0);
      setPageError(
        error instanceof Error ? error.message : "Unable to load meter events.",
      );
    } finally {
      setIsLoadingEvents(false);
    }
  }, [authorizedFetch, meterId]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  const overviewCards = useMemo(
    () => [
      {
        label: "Visible meter events",
        value: String(events.length),
        note:
          totalEvents > events.length
            ? `${totalEvents} persisted events match this meter`
            : "Current bounded meter event result set",
      },
      {
        label: "Critical or open items",
        value: String(
          events.filter(
            (item) =>
              item.severity.toLowerCase() === "critical" ||
              item.event_state.toLowerCase() === "open",
          ).length,
        ),
        note: "Immediate operator attention in the current event slice",
      },
      {
        label: "Latest occurred activity",
        value: events[0] ? formatDateTime(events[0].occurred_at) : "Not available",
        note: events[0] ? formatLabel(events[0].event_name ?? events[0].event_code) : "No meter event history yet",
      },
    ],
    [events, totalEvents],
  );

  return (
    <div className="detail-stack">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <section className="subpanel audit-center-overview-panel">
        <div className="section-heading">
          <div>
            <h2>Meter events visibility</h2>
            <p className="muted">
              Meter-scoped event and alert visibility using the existing ingested event history.
            </p>
          </div>
          <span className="artifact-pill">
            {isLoadingEvents
              ? "Loading meter events"
              : `${totalEvents} meter event${totalEvents === 1 ? "" : "s"}`}
          </span>
        </div>

        {isLoadingEvents ? <p className="muted">Loading meter events...</p> : null}

        {!isLoadingEvents ? (
          <div className="detail-stack">
            <div className="audit-center-overview-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card audit-center-overview-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>

            <div className="artifact-row">
              <span className="artifact-pill">Primary source ingested meter events</span>
              <span className="artifact-pill">Occurred time first</span>
              <span className="artifact-pill">Existing persistence only</span>
            </div>
          </div>
        ) : null}
      </section>

      <section className="subpanel">
        <div className="section-heading">
          <div>
            <h2>Meter event feed</h2>
            <p className="muted">
              Scan recent events and alert-like signals for this meter with severity, state,
              and lightweight event detail.
            </p>
          </div>
          <div className="artifact-row">
            <span className="artifact-pill">
              {events.length} visible row{events.length === 1 ? "" : "s"}
            </span>
            <Link className="secondary-button" href="/jobs-events-alerts">
              Open jobs / events / alerts
            </Link>
          </div>
        </div>

        {isLoadingEvents ? (
          <p className="muted">Loading meter event feed...</p>
        ) : events.length === 0 ? (
          <section className="audit-center-empty-state">
            <p className="eyebrow">Meter Events Empty</p>
            <h3>No ingested events are currently tied to this meter</h3>
            <p className="muted">
              Event visibility will appear here when persisted meter event rows are available
              for this operational record.
            </p>
          </section>
        ) : (
          <div className="readings-table-shell">
            <table className="readings-table audit-center-table">
              <thead>
                <tr>
                  <th scope="col">Timestamp</th>
                  <th scope="col">Event</th>
                  <th scope="col">Severity</th>
                  <th scope="col">State</th>
                  <th scope="col">Source</th>
                  <th scope="col">Summary</th>
                </tr>
              </thead>
              <tbody>
                {events.map((item) => (
                  <tr key={item.id}>
                    <td>{formatDateTime(item.occurred_at)}</td>
                    <td>
                      <strong>{item.event_name ?? formatLabel(item.event_code)}</strong>
                      <div className="muted">{item.event_code}</div>
                    </td>
                    <td>
                      <span className={`status-pill ${buildStatusTone(item.severity)}`}>
                        {formatLabel(item.severity)}
                      </span>
                    </td>
                    <td>
                      <span className={`status-pill ${buildStatusTone(item.event_state)}`}>
                        {formatLabel(item.event_state)}
                      </span>
                    </td>
                    <td>
                      <strong>{item.related_attempt_id ? "Attempt" : item.related_batch_id ? "Batch" : "Meter event"}</strong>
                      <div className="muted">{item.related_attempt_id ?? item.related_batch_id ?? item.meter_id ?? "No source recorded"}</div>
                    </td>
                    <td>
                      <div>{buildEventSummary(item)}</div>
                      <div className="artifact-row" style={{ marginTop: "0.6rem" }}>
                        <Link
                          className="secondary-button"
                          href={buildActivityDetailHref("event", item.id)}
                        >
                          Open activity detail
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
