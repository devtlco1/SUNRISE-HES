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

function formatLatestSessionSummary(session: ConnectivitySession | null): string {
  if (!session) {
    return "No recent session";
  }
  return `${session.status} (${session.session_purpose})`;
}

function formatStatusLabel(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildStatusTone(value: string | null): "positive" | "warning" | "danger" | "neutral" {
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
    normalized.includes("queued")
  ) {
    return "warning";
  }
  return "neutral";
}

export function ConnectivityModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [rows, setRows] = useState<ConnectivityOverviewRow[]>([]);
  const [selectedMeterId, setSelectedMeterId] = useState<string | null>(null);
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
    const withoutRecentSession = rows.filter((row) => row.latestSession === null).length;

    return {
      metersWithEndpoint,
      metersWithSignal,
      latestSucceeded,
      withoutRecentSession,
    };
  }, [rows]);

  const selectedRow = useMemo(
    () => rows.find((row) => row.meter.id === selectedMeterId) ?? rows[0] ?? null,
    [rows, selectedMeterId],
  );

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
        label: "Without recent session",
        value: String(overviewStats.withoutRecentSession),
        note: "No recent connectivity session recorded",
      },
      {
        label: "Selected meter",
        value: selectedRow?.meter.serial_number ?? "No selection",
        note: selectedRow
          ? formatLatestSessionSummary(selectedRow.latestSession)
          : "Inspect a meter to review connectivity context",
      },
    ],
    [overviewStats, rows.length, selectedRow, totalMeters],
  );

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
                    <span className="artifact-pill">
                      {formatFreshnessHint(selectedRow.meter.last_seen_at)}
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
