"use client";

import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

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

type AuditFilters = {
  action: string;
  actor: string;
  entityType: string;
  outcome: string;
  fromCreatedAt: string;
  toCreatedAt: string;
};

const EMPTY_FILTERS: AuditFilters = {
  action: "",
  actor: "",
  entityType: "",
  outcome: "",
  fromCreatedAt: "",
  toCreatedAt: "",
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

function formatCountLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function formatActor(item: AuditLogItem): string {
  return item.actor_full_name ?? item.actor_username ?? "System";
}

function formatEntity(item: AuditLogItem): string {
  const entityLabel = formatLabel(item.entity_type);
  if (!item.entity_id) {
    return entityLabel;
  }
  return `${entityLabel} • ${item.entity_id}`;
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

function buildAuditLogQuery(filters: AuditFilters): string {
  const searchParams = new URLSearchParams({
    offset: "0",
    limit: "50",
  });
  if (filters.action.trim()) {
    searchParams.set("action", filters.action.trim());
  }
  if (filters.actor.trim()) {
    searchParams.set("actor", filters.actor.trim());
  }
  if (filters.entityType.trim()) {
    searchParams.set("entity_type", filters.entityType.trim());
  }
  if (filters.outcome.trim()) {
    searchParams.set("outcome", filters.outcome.trim());
  }
  if (filters.fromCreatedAt) {
    searchParams.set("from_created_at", new Date(filters.fromCreatedAt).toISOString());
  }
  if (filters.toCreatedAt) {
    searchParams.set("to_created_at", new Date(filters.toCreatedAt).toISOString());
  }
  return `/api/v1/audit-logs?${searchParams.toString()}`;
}

export function AuditCenterModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [totalAuditLogs, setTotalAuditLogs] = useState(0);
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingAuditLogs, setIsLoadingAuditLogs] = useState(false);

  const loadAuditLogs = useCallback(async () => {
    setIsLoadingAuditLogs(true);
    setPageError(null);

    try {
      const response = await authorizedFetch<AuditLogListResponse>(
        buildAuditLogQuery(appliedFilters),
      );
      setAuditLogs(response.items);
      setTotalAuditLogs(response.total);
    } catch (error) {
      setAuditLogs([]);
      setTotalAuditLogs(0);
      setPageError(
        error instanceof Error ? error.message : "Unable to load audit center records.",
      );
    } finally {
      setIsLoadingAuditLogs(false);
    }
  }, [appliedFilters, authorizedFetch]);

  useEffect(() => {
    void loadAuditLogs();
  }, [loadAuditLogs]);

  const overviewCards = useMemo(
    () => [
      {
        label: "Visible audit records",
        value: String(auditLogs.length),
        note:
          totalAuditLogs > auditLogs.length
            ? `${formatCountLabel(totalAuditLogs, "record", "records")} match the current bounded query`
            : "Current bounded result set",
      },
      {
        label: "Actors represented",
        value: String(new Set(auditLogs.map((item) => formatActor(item))).size),
        note: "Distinct users or system contexts in view",
      },
      {
        label: "Actions represented",
        value: String(new Set(auditLogs.map((item) => item.action)).size),
        note: "Unique action codes in the current result set",
      },
      {
        label: "Failure outcomes",
        value: String(
          auditLogs.filter((item) => item.payload?.outcome?.toLowerCase() === "failure").length,
        ),
        note: "Immediate scan of failed or rejected outcomes in view",
      },
      {
        label: "Entity types represented",
        value: String(new Set(auditLogs.map((item) => item.entity_type)).size),
        note: "Distinct bounded entity types currently visible",
      },
      {
        label: "Newest visible activity",
        value: auditLogs[0] ? formatDateTime(auditLogs[0].created_at) : "Not available",
        note: auditLogs[0] ? formatLabel(auditLogs[0].action) : "No visible audit activity yet",
      },
    ],
    [auditLogs, totalAuditLogs],
  );

  const appliedFilterBadges = useMemo(() => {
    const badges: string[] = [];
    if (appliedFilters.action.trim()) {
      badges.push(`Action ${appliedFilters.action.trim()}`);
    }
    if (appliedFilters.actor.trim()) {
      badges.push(`Actor ${appliedFilters.actor.trim()}`);
    }
    if (appliedFilters.entityType.trim()) {
      badges.push(`Entity ${appliedFilters.entityType.trim()}`);
    }
    if (appliedFilters.outcome.trim()) {
      badges.push(`Outcome ${formatLabel(appliedFilters.outcome.trim())}`);
    }
    if (appliedFilters.fromCreatedAt) {
      badges.push(`From ${formatDateTime(new Date(appliedFilters.fromCreatedAt).toISOString())}`);
    }
    if (appliedFilters.toCreatedAt) {
      badges.push(`To ${formatDateTime(new Date(appliedFilters.toCreatedAt).toISOString())}`);
    }
    return badges;
  }, [appliedFilters]);

  const handleApplyFilters = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setAppliedFilters(filters);
    },
    [filters],
  );

  const handleClearFilters = useCallback(() => {
    setFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
  }, []);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel audit-center-overview-panel">
          <div className="section-heading">
            <div>
              <h2>Audit traceability center</h2>
              <p className="muted">
                Unified operational audit visibility over the currently persisted auth,
                command, job, meter, connectivity, and readings activity.
              </p>
            </div>
            <span className="artifact-pill">
              {isLoadingAuditLogs
                ? "Loading current audit feed"
                : `${formatCountLabel(totalAuditLogs, "record", "records")} available`}
            </span>
          </div>

          {isLoadingAuditLogs ? <p className="muted">Loading audit center records...</p> : null}

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
                <span className="artifact-pill">Primary source audit_logs</span>
                <span className="artifact-pill">Newest records first</span>
                <span className="artifact-pill">Existing persistence only</span>
              </div>
            </div>
          ) : null}
        </section>

        <div className="audit-center-layout">
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Audit filters</h2>
                <p className="muted">
                  Narrow the bounded audit feed by actor, action, entity type, outcome,
                  and visible time window.
                </p>
              </div>
            </div>

            <form className="detail-stack" onSubmit={handleApplyFilters}>
              <div className="inline-form">
                <label className="field">
                  <span>Action filter</span>
                  <input
                    aria-label="Action filter"
                    onChange={(event) =>
                      setFilters((current) => ({ ...current, action: event.target.value }))
                    }
                    placeholder="commands.approvals.approve"
                    type="search"
                    value={filters.action}
                  />
                </label>

                <label className="field">
                  <span>Actor filter</span>
                  <input
                    aria-label="Actor filter"
                    onChange={(event) =>
                      setFilters((current) => ({ ...current, actor: event.target.value }))
                    }
                    placeholder="ops.user"
                    type="search"
                    value={filters.actor}
                  />
                </label>

                <label className="field">
                  <span>Entity type filter</span>
                  <input
                    aria-label="Entity type filter"
                    onChange={(event) =>
                      setFilters((current) => ({ ...current, entityType: event.target.value }))
                    }
                    placeholder="commands"
                    type="search"
                    value={filters.entityType}
                  />
                </label>

                <label className="field">
                  <span>Outcome</span>
                  <select
                    aria-label="Outcome filter"
                    onChange={(event) =>
                      setFilters((current) => ({ ...current, outcome: event.target.value }))
                    }
                    value={filters.outcome}
                  >
                    <option value="">All outcomes</option>
                    <option value="success">Success</option>
                    <option value="failure">Failure</option>
                  </select>
                </label>
              </div>

              <div className="inline-form">
                <label className="field">
                  <span>From</span>
                  <input
                    aria-label="From timestamp"
                    onChange={(event) =>
                      setFilters((current) => ({
                        ...current,
                        fromCreatedAt: event.target.value,
                      }))
                    }
                    type="datetime-local"
                    value={filters.fromCreatedAt}
                  />
                </label>

                <label className="field">
                  <span>To</span>
                  <input
                    aria-label="To timestamp"
                    onChange={(event) =>
                      setFilters((current) => ({
                        ...current,
                        toCreatedAt: event.target.value,
                      }))
                    }
                    type="datetime-local"
                    value={filters.toCreatedAt}
                  />
                </label>
              </div>

              <div className="artifact-row">
                <button className="primary-button" type="submit">
                  Apply filters
                </button>
                <button className="secondary-button" onClick={handleClearFilters} type="button">
                  Clear filters
                </button>
              </div>
            </form>

            <div className="artifact-row">
              {appliedFilterBadges.length === 0 ? (
                <span className="artifact-pill">No bounded filters applied</span>
              ) : (
                appliedFilterBadges.map((badge) => (
                  <span key={badge} className="artifact-pill">
                    {badge}
                  </span>
                ))
              )}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Audit feed</h2>
                <p className="muted">
                  Scan who acted, what happened, which entity was involved, and whether the
                  recorded outcome succeeded or failed.
                </p>
              </div>
              <span className="artifact-pill">
                {formatCountLabel(auditLogs.length, "visible row", "visible rows")}
              </span>
            </div>

            {isLoadingAuditLogs ? (
              <p className="muted">Loading audit feed...</p>
            ) : auditLogs.length === 0 ? (
              <section className="audit-center-empty-state">
                <p className="eyebrow">Audit Feed Empty</p>
                <h3>No audit records match the current bounded query</h3>
                <p className="muted">
                  Adjust or clear the current filters to restore persisted traceability rows.
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
                        <td>
                          <strong>{formatDateTime(item.created_at)}</strong>
                          <div className="muted">
                            {item.request_id ? `Request ${item.request_id}` : "Request ID unavailable"}
                          </div>
                        </td>
                        <td>
                          <strong>{formatActor(item)}</strong>
                          <div className="muted">
                            {item.actor_username
                              ? `${item.actor_username}${item.ip_address ? ` • ${item.ip_address}` : ""}`
                              : item.ip_address ?? "System context"}
                          </div>
                        </td>
                        <td>
                          <strong>{formatLabel(item.action)}</strong>
                          <div className="muted">
                            {item.payload?.http.method ?? "Request"} {item.payload?.http.path ?? "Path unavailable"}
                          </div>
                        </td>
                        <td>
                          <strong>{formatEntity(item)}</strong>
                          <div className="muted">{item.entity_id ?? "No entity ID recorded"}</div>
                        </td>
                        <td>
                          <span className={`status-pill ${buildStatusTone(item.payload?.outcome ?? null)}`}>
                            {formatLabel(item.payload?.outcome ?? null)}
                          </span>
                        </td>
                        <td>
                          <strong>{buildSummary(item)}</strong>
                          <div className="muted">
                            {item.payload?.details
                              ? Object.entries(item.payload.details)
                                  .slice(0, 2)
                                  .map(([key, value]) => `${formatLabel(key)} ${formatDetailValue(value)}`)
                                  .join(" • ")
                              : "No bounded detail payload recorded"}
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
      </div>
    </section>
  );
}
