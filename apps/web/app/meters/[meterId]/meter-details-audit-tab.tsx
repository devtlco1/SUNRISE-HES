"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../../operational-shell";

type AuditPayload = {
  outcome: string;
  http: {
    method: string | null;
    path: string | null;
    user_agent: string | null;
  };
  details: Record<string, unknown> | null;
};

type AuditLogItem = {
  id: string;
  created_at: string;
  actor_user_id: string | null;
  actor_username: string | null;
  actor_full_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  request_id: string | null;
  ip_address: string | null;
  description: string | null;
  payload: AuditPayload | null;
};

type AuditLogListResponse = {
  total: number;
  items: AuditLogItem[];
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

function formatLabel(value: string | null): string {
  if (!value) {
    return "Not recorded";
  }

  return value
    .split(/[._]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatActor(item: AuditLogItem): string {
  return item.actor_full_name ?? item.actor_username ?? "System";
}

function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "Not available";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function buildStatusTone(value: string | null): "positive" | "warning" | "danger" | "neutral" {
  const normalized = value?.toLowerCase() ?? "";
  if (normalized.includes("success") || normalized.includes("succeed")) {
    return "positive";
  }
  if (normalized.includes("failure") || normalized.includes("fail") || normalized.includes("error")) {
    return "danger";
  }
  if (normalized.includes("pending") || normalized.includes("review")) {
    return "warning";
  }
  return "neutral";
}

function buildSummary(item: AuditLogItem): string {
  if (item.description) {
    return item.description;
  }

  const detailEntries = Object.entries(item.payload?.details ?? {}).slice(0, 2);
  if (detailEntries.length > 0) {
    return detailEntries
      .map(([key, value]) => `${formatLabel(key)} ${formatDetailValue(value)}`)
      .join(" • ");
  }

  if (item.payload?.http.path) {
    return `${item.payload.http.method ?? "Request"} ${item.payload.http.path}`;
  }

  return "No bounded summary recorded.";
}

function buildMeterAuditLogQuery(meterId: string): string {
  const searchParams = new URLSearchParams({
    offset: "0",
    limit: "12",
    entity_type: "meters",
    entity_id: meterId,
  });
  return `/api/v1/audit-logs?${searchParams.toString()}`;
}

export function MeterDetailsAuditTab({
  meterId,
  authorizedFetch,
}: {
  meterId: string;
  authorizedFetch: AuthorizedFetch;
}) {
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [totalAuditLogs, setTotalAuditLogs] = useState(0);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingAuditLogs, setIsLoadingAuditLogs] = useState(false);

  const loadAuditLogs = useCallback(async () => {
    setIsLoadingAuditLogs(true);
    setPageError(null);

    try {
      const response = await authorizedFetch<AuditLogListResponse>(
        buildMeterAuditLogQuery(meterId),
      );
      setAuditLogs(response.items);
      setTotalAuditLogs(response.total);
    } catch (error) {
      setAuditLogs([]);
      setTotalAuditLogs(0);
      setPageError(
        error instanceof Error ? error.message : "Unable to load meter audit history.",
      );
    } finally {
      setIsLoadingAuditLogs(false);
    }
  }, [authorizedFetch, meterId]);

  useEffect(() => {
    void loadAuditLogs();
  }, [loadAuditLogs]);

  const overviewCards = useMemo(
    () => [
      {
        label: "Visible meter audit rows",
        value: String(auditLogs.length),
        note:
          totalAuditLogs > auditLogs.length
            ? `${totalAuditLogs} persisted rows match this meter scope`
            : "Current bounded meter audit result set",
      },
      {
        label: "Actors represented",
        value: String(new Set(auditLogs.map((item) => formatActor(item))).size),
        note: "Distinct users or system contexts in the meter audit view",
      },
      {
        label: "Latest meter activity",
        value: auditLogs[0] ? formatDateTime(auditLogs[0].created_at) : "Not available",
        note: auditLogs[0] ? formatLabel(auditLogs[0].action) : "No meter-scoped audit activity yet",
      },
    ],
    [auditLogs, totalAuditLogs],
  );

  return (
    <div className="detail-stack">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <section className="subpanel audit-center-overview-panel">
        <div className="section-heading">
          <div>
            <h2>Meter audit traceability</h2>
            <p className="muted">
              Meter-scoped audit view over the existing persisted `audit_logs` history for
              this operational record.
            </p>
          </div>
          <span className="artifact-pill">
            {isLoadingAuditLogs
              ? "Loading meter audit feed"
              : `${totalAuditLogs} meter audit row${totalAuditLogs === 1 ? "" : "s"}`}
          </span>
        </div>

        {isLoadingAuditLogs ? <p className="muted">Loading meter audit history...</p> : null}

        {!isLoadingAuditLogs ? (
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
              <span className="artifact-pill">Scoped to entity type meters</span>
              <span className="artifact-pill">Current meter only</span>
              <span className="artifact-pill">Existing persistence only</span>
            </div>
          </div>
        ) : null}
      </section>

      <section className="subpanel">
        <div className="section-heading">
          <div>
            <h2>Meter audit feed</h2>
            <p className="muted">
              Scan what happened to this meter, who initiated it, and whether the recorded
              outcome succeeded or failed.
            </p>
          </div>
          <div className="artifact-row">
            <span className="artifact-pill">
              {auditLogs.length} visible row{auditLogs.length === 1 ? "" : "s"}
            </span>
            <Link className="secondary-button" href="/audit-center">
              Open audit center
            </Link>
          </div>
        </div>

        {isLoadingAuditLogs ? (
          <p className="muted">Loading meter audit feed...</p>
        ) : auditLogs.length === 0 ? (
          <section className="audit-center-empty-state">
            <p className="eyebrow">Meter Audit Empty</p>
            <h3>No audit records are currently tied to this meter</h3>
            <p className="muted">
              Meter-scoped traceability will appear here when persisted audit rows reference
              this meter entity directly.
            </p>
          </section>
        ) : (
          <div className="readings-table-shell">
            <table className="readings-table audit-center-table">
              <thead>
                <tr>
                  <th scope="col">Timestamp</th>
                  <th scope="col">Actor</th>
                  <th scope="col">Action</th>
                  <th scope="col">Target</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Summary</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((item) => (
                  <tr key={item.id}>
                    <td>{formatDateTime(item.created_at)}</td>
                    <td>
                      <strong>{formatActor(item)}</strong>
                      <div className="muted">{item.actor_username ?? "System"}</div>
                    </td>
                    <td>{formatLabel(item.action)}</td>
                    <td>
                      <strong>{formatLabel(item.entity_type)}</strong>
                      <div className="muted">{item.entity_id ?? "No entity ID recorded"}</div>
                    </td>
                    <td>
                      <span className={`status-pill ${buildStatusTone(item.payload?.outcome ?? null)}`}>
                        {formatLabel(item.payload?.outcome ?? null)}
                      </span>
                    </td>
                    <td>{buildSummary(item)}</td>
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
