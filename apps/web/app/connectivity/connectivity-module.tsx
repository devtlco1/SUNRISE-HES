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

export function ConnectivityModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [rows, setRows] = useState<ConnectivityOverviewRow[]>([]);
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

      setRows(
        rowResults.map(({ meter, primaryEndpoint, latestSession }) => ({
          meter,
          primaryEndpoint,
          latestSession,
        })),
      );
      setTotalMeters(metersResponse.total);

      if (rowResults.some((item) => item.contextUnavailable)) {
        setPageError("Unable to load complete connectivity overview context.");
      }
    } catch (error) {
      setRows([]);
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

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Connectivity overview</h2>
              <p className="muted">
                Compact operational visibility into current meter connectivity
                context.
              </p>
            </div>
            <span className="artifact-pill">{totalMeters} meters in scope</span>
          </div>

          {isLoadingOverview ? (
            <p className="muted">Loading connectivity overview...</p>
          ) : null}

          {!isLoadingOverview ? (
            <div className="meter-summary-grid">
              <div className="stat-card">
                <span className="stat-label">Meters in result set</span>
                <strong>{rows.length}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">With active endpoint hint</span>
                <strong>{overviewStats.metersWithEndpoint}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">With recent signal</span>
                <strong>{overviewStats.metersWithSignal}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Latest session succeeded</span>
                <strong>{overviewStats.latestSucceeded}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Without recent session</span>
                <strong>{overviewStats.withoutRecentSession}</strong>
              </div>
            </div>
          ) : null}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Connectivity-focused meters</h2>
              <p className="muted">
                Select a row to continue into the existing meter details
                operational page.
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
              <Link
                key={row.meter.id}
                className="meter-list-item"
                href={`/meters/${row.meter.id}`}
              >
                <div className="command-list-item-header">
                  <strong>{row.meter.serial_number}</strong>
                  <span className="status-pill">{row.meter.current_status}</span>
                </div>
                <div className="command-list-item-meta">
                  <span>Meter ID {row.meter.id}</span>
                  <span>
                    {row.meter.communication_profile_code ??
                      row.meter.meter_profile_code ??
                      "No communication summary"}
                  </span>
                </div>
                <div className="command-list-item-meta">
                  <span>
                    {row.primaryEndpoint?.endpoint_display_name ??
                      row.primaryEndpoint?.endpoint_code ??
                      "No active endpoint"}
                  </span>
                  <span>{formatLatestSessionSummary(row.latestSession)}</span>
                </div>
                <div className="command-list-item-meta">
                  <span>{formatFreshnessHint(row.meter.last_seen_at)}</span>
                  <span>Last seen {formatDateTime(row.meter.last_seen_at)}</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
