"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { classifyReachabilityFromLastSeen } from "../../dashboard/dashboard-utils";
import type { AuthorizedFetch } from "../../session-provider";
import { useSession } from "../../session-provider";
import { WorkspaceShell } from "../../workspace-shell";

type MeterDetailResponse = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  badge_number: string | null;
  manufacturer_id: string;
  manufacturer_code: string;
  meter_model_id: string;
  meter_model_code: string;
  firmware_version_id: string | null;
  firmware_version: string | null;
  communication_profile_id: string | null;
  communication_profile_code: string | null;
  meter_profile_id: string | null;
  meter_profile_code: string | null;
  current_status: string;
  transformer_id: string | null;
  service_point_id: string | null;
  notes: string | null;
  is_active: boolean;
  installed_at: string | null;
  commissioned_at: string | null;
  last_seen_at: string | null;
  metadata_json: Record<string, unknown> | null;
  status_history: Array<{
    id: string;
    previous_status: string | null;
    new_status: string;
    changed_by_user_id: string | null;
    reason: string | null;
    changed_at: string;
  }>;
};

type MeterReadingListResponse = {
  total: number;
  items: Array<{
    id: string;
    obis_code: string;
    reading_type: string;
    value_numeric: string | null;
    value_text: string | null;
    value_timestamp: string | null;
    unit: string | null;
    quality: string | null;
    captured_at: string;
  }>;
};

type MeterScopedCommandOperationalRecentListResponse = {
  meter_id: string;
  total: number;
  limit: number;
  items: Array<{
    command_id: string;
    command_family: string;
    command_category: string;
    command_status: string;
    approval_status: string;
    command_template_code: string;
    latest_command_execution_attempt_status: string | null;
    created_at: string;
    latest_updated_at: string;
  }>;
};

type MeterEndpointAssignmentListResponse = {
  total: number;
  items: Array<{
    id: string;
    endpoint_code: string;
    endpoint_display_name: string;
    assigned_at: string;
    unassigned_at: string | null;
    is_primary: boolean;
    assignment_status: string;
    notes: string | null;
  }>;
};

type ConnectivitySessionHistoryListResponse = {
  total: number;
  items: Array<{
    id: string;
    started_at: string;
    ended_at: string | null;
    status: string;
    session_purpose: string;
    error_code: string | null;
    error_message: string | null;
    bytes_sent: number | null;
    bytes_received: number | null;
  }>;
};

type AuditLogListResponse = {
  total: number;
  items: Array<{
    id: string;
    created_at: string;
    actor_username: string | null;
    action: string;
    description: string | null;
  }>;
};

type MeterConsumerLinkageResponse = {
  meter_id: string;
  linkage_status: string;
  linkage_source: string | null;
  consumer_display_name: string | null;
  consumer_type: string | null;
  account_number: string | null;
  service_point_code: string | null;
};

type GisLiteEntityListResponse = {
  total: number;
  items: Array<{
    meter_id: string;
    has_coordinates: boolean;
    latitude: number | null;
    longitude: number | null;
    address_line: string | null;
    service_point_code: string | null;
    meter_last_seen_at: string | null;
  }>;
};

type TabId =
  | "summary"
  | "connectivity"
  | "readings"
  | "commands"
  | "audit"
  | "consumer"
  | "gis";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "summary", label: "Summary" },
  { id: "connectivity", label: "Connectivity" },
  { id: "readings", label: "Readings" },
  { id: "commands", label: "Commands" },
  { id: "audit", label: "Audit" },
  { id: "consumer", label: "Consumer" },
  { id: "gis", label: "GIS" },
];

function isUuid(s: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s.trim());
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) {
    return "—";
  }
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function humanizeEnum(s: string): string {
  return s.replace(/_/g, " ");
}

function shortId(id: string): string {
  return `${id.slice(0, 8)}…`;
}

function normId(s: string | null | undefined): string {
  return (s ?? "").trim().toLowerCase();
}

async function fetchOptional<T>(
  authorizedFetch: AuthorizedFetch,
  path: string,
): Promise<{ ok: true; data: T } | { ok: false; message: string }> {
  try {
    const data = await authorizedFetch<T>(path);
    return { ok: true, data };
  } catch (e) {
    return {
      ok: false,
      message: e instanceof Error ? e.message : "Request failed.",
    };
  }
}

type Loaded<T> =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "ok"; data: T }
  | { state: "err"; message: string };

function lifecycleTone(status: string): "success" | "info" | "muted" {
  if (status === "active") {
    return "success";
  }
  if (status === "registered" || status === "commissioned") {
    return "info";
  }
  return "muted";
}

function reachTone(bucket: ReturnType<typeof classifyReachabilityFromLastSeen>): "success" | "danger" | "muted" {
  if (bucket === "online") {
    return "success";
  }
  if (bucket === "offline") {
    return "danger";
  }
  return "muted";
}

function DetailField({
  label,
  value,
  mono,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <Fragment>
      <dt className="ws-meter-detail-dt">{label}</dt>
      <dd className={`ws-meter-detail-dd${mono ? " ws-meter-detail-dd--mono" : ""}`}>{value}</dd>
    </Fragment>
  );
}

export function MeterDetailClient({ meterId }: { meterId: string }) {
  return (
    <WorkspaceShell>
      <MeterDetailBody meterId={meterId} />
    </WorkspaceShell>
  );
}

function MeterDetailBody({ meterId }: { meterId: string }) {
  const { currentUser, isCheckingSession, authorizedFetch } = useSession();
  const [tab, setTab] = useState<TabId>("summary");
  const [meter, setMeter] = useState<Loaded<MeterDetailResponse>>({ state: "idle" });
  const [readings, setReadings] = useState<Loaded<MeterReadingListResponse>>({ state: "idle" });
  const [commands, setCommands] = useState<Loaded<MeterScopedCommandOperationalRecentListResponse>>({
    state: "idle",
  });
  const [assignments, setAssignments] = useState<Loaded<MeterEndpointAssignmentListResponse>>({
    state: "idle",
  });
  const [sessions, setSessions] = useState<Loaded<ConnectivitySessionHistoryListResponse>>({
    state: "idle",
  });
  const [audit, setAudit] = useState<Loaded<AuditLogListResponse>>({ state: "idle" });
  const [linkage, setLinkage] = useState<Loaded<MeterConsumerLinkageResponse>>({ state: "idle" });
  const [gis, setGis] = useState<Loaded<GisLiteEntityListResponse>>({ state: "idle" });

  const validId = isUuid(meterId);

  const loadSecondary = useCallback(
    async (id: string) => {
      const enc = encodeURIComponent(id);
      const [r, c, a, s, au, li, g] = await Promise.all([
        fetchOptional<MeterReadingListResponse>(
          authorizedFetch,
          `/api/v1/meters/${enc}/readings?limit=75`,
        ),
        fetchOptional<MeterScopedCommandOperationalRecentListResponse>(
          authorizedFetch,
          `/api/v1/meters/${enc}/commands/recent?limit=40`,
        ),
        fetchOptional<MeterEndpointAssignmentListResponse>(
          authorizedFetch,
          `/api/v1/meters/${enc}/endpoint-assignments`,
        ),
        fetchOptional<ConnectivitySessionHistoryListResponse>(
          authorizedFetch,
          `/api/v1/meters/${enc}/sessions?limit=25`,
        ),
        fetchOptional<AuditLogListResponse>(
          authorizedFetch,
          `/api/v1/audit-logs?entity_type=meters&entity_id=${enc}&limit=40`,
        ),
        fetchOptional<MeterConsumerLinkageResponse>(
          authorizedFetch,
          `/api/v1/meters/${enc}/consumer-linkage`,
        ),
        fetchOptional<GisLiteEntityListResponse>(
          authorizedFetch,
          `/api/v1/gis-lite/entities?meter_id=${enc}&limit=5`,
        ),
      ]);

      setReadings(r.ok ? { state: "ok", data: r.data } : { state: "err", message: r.message });
      setCommands(c.ok ? { state: "ok", data: c.data } : { state: "err", message: c.message });
      setAssignments(a.ok ? { state: "ok", data: a.data } : { state: "err", message: a.message });
      setSessions(s.ok ? { state: "ok", data: s.data } : { state: "err", message: s.message });
      setAudit(au.ok ? { state: "ok", data: au.data } : { state: "err", message: au.message });
      setLinkage(li.ok ? { state: "ok", data: li.data } : { state: "err", message: li.message });
      setGis(g.ok ? { state: "ok", data: g.data } : { state: "err", message: g.message });
    },
    [authorizedFetch],
  );

  useEffect(() => {
    if (!currentUser || !validId) {
      return;
    }
    let cancelled = false;
    (async () => {
      setMeter({ state: "loading" });
      setReadings({ state: "loading" });
      setCommands({ state: "loading" });
      setAssignments({ state: "loading" });
      setSessions({ state: "loading" });
      setAudit({ state: "loading" });
      setLinkage({ state: "loading" });
      setGis({ state: "loading" });
      const enc = encodeURIComponent(meterId);
      const res = await fetchOptional<MeterDetailResponse>(authorizedFetch, `/api/v1/meters/${enc}`);
      if (cancelled) {
        return;
      }
      if (!res.ok) {
        setMeter({ state: "err", message: res.message });
        setReadings({ state: "idle" });
        setCommands({ state: "idle" });
        setAssignments({ state: "idle" });
        setSessions({ state: "idle" });
        setAudit({ state: "idle" });
        setLinkage({ state: "idle" });
        setGis({ state: "idle" });
        return;
      }
      setMeter({ state: "ok", data: res.data });
      void loadSecondary(meterId);
    })();
    return () => {
      cancelled = true;
    };
  }, [authorizedFetch, currentUser, loadSecondary, meterId, validId]);

  const nowMs = Date.now();
  const m = meter.state === "ok" ? meter.data : null;
  const reachBucket = m ? classifyReachabilityFromLastSeen(m.last_seen_at, nowMs) : "unknown";
  const gisRow = gis.state === "ok" && gis.data.items[0] ? gis.data.items[0] : null;

  const latestReadAt = useMemo(() => {
    if (readings.state !== "ok" || readings.data.items.length === 0) {
      return null;
    }
    const first = readings.data.items[0];
    return first.captured_at;
  }, [readings]);

  if (isCheckingSession) {
    return <p className="ws-muted">Checking session…</p>;
  }

  if (!currentUser) {
    return (
      <div className="ws-canvas ws-canvas--gate">
        <p className="ws-muted">Sign in to view this meter.</p>
        <Link href="/login" className="ws-btn ws-btn-primary">
          Sign in
        </Link>
      </div>
    );
  }

  if (!validId) {
    return (
      <div className="ws-meter-detail">
        <p className="ws-dash-banner" role="alert">
          Invalid meter identifier.
        </p>
        <Link href="/meters" className="ws-btn ws-btn-ghost">
          Back to meters
        </Link>
      </div>
    );
  }

  if (meter.state === "loading" || meter.state === "idle") {
    return <p className="ws-dash-loading">Loading meter…</p>;
  }

  if (meter.state === "err") {
    const notFound = /404/.test(meter.message);
    return (
      <div className="ws-meter-detail">
        <p className="ws-dash-banner" role="alert">
          {notFound ? "Meter not found." : meter.message}
        </p>
        <Link href="/meters" className="ws-btn ws-btn-ghost">
          Back to meters
        </Link>
      </div>
    );
  }

  const detail = meter.data;
  const serialNorm = normId(detail.serial_number);
  const headerUtility =
    detail.utility_meter_number && normId(detail.utility_meter_number) !== serialNorm
      ? detail.utility_meter_number
      : null;
  const headerBadge =
    detail.badge_number &&
    normId(detail.badge_number) !== serialNorm &&
    normId(detail.badge_number) !== normId(headerUtility)
      ? detail.badge_number
      : null;

  return (
    <div className="ws-meter-detail">
        <div className="ws-meter-detail-breadcrumb">
          <Link href="/meters" className="ws-meter-detail-back">
            Meters
          </Link>
          <span className="ws-meter-detail-bc-sep" aria-hidden>
            /
          </span>
          <span className="ws-meter-detail-bc-static">Meter detail</span>
        </div>

        <header className="ws-meter-detail-header">
          <div className="ws-meter-detail-header-main">
            <h1 className="ws-meter-detail-title">{detail.serial_number}</h1>
            <p className="ws-meter-detail-sub">
              <span className="ws-meter-detail-sub-mono" title={detail.id}>
                ID {shortId(detail.id)}
              </span>
              <span className="ws-meter-detail-sub-sep" aria-hidden>
                ·
              </span>
              <span>
                {detail.manufacturer_code} · {detail.meter_model_code}
              </span>
              {headerUtility ? (
                <>
                  <span className="ws-meter-detail-sub-sep" aria-hidden>
                    ·
                  </span>
                  <span className="ws-meter-detail-sub-mono">U# {headerUtility}</span>
                </>
              ) : null}
              {headerBadge ? (
                <>
                  <span className="ws-meter-detail-sub-sep" aria-hidden>
                    ·
                  </span>
                  <span className="ws-meter-detail-sub-mono">Badge {headerBadge}</span>
                </>
              ) : null}
            </p>
            <div className="ws-meter-detail-header-chips" aria-label="Status">
              <span className={`ws-chip ws-chip--${lifecycleTone(detail.current_status)}`}>
                {humanizeEnum(detail.current_status)}
              </span>
              <span className={`ws-chip ws-chip--${reachTone(reachBucket)}`}>
                {reachBucket === "online"
                  ? "Online"
                  : reachBucket === "offline"
                    ? "Stale"
                    : "Unknown"}
              </span>
              <span className={`ws-chip ws-chip--${detail.is_active ? "success" : "muted"}`}>
                {detail.is_active ? "Active" : "Inactive"}
              </span>
              {gisRow ? (
                <span
                  className={`ws-chip ws-chip--${gisRow.has_coordinates ? "success" : "muted"}`}
                >
                  {gisRow.has_coordinates ? "Mapped" : "Unmapped"}
                </span>
              ) : null}
            </div>
            <p className="ws-meter-detail-meta-line">
              <span>Last seen {formatWhen(detail.last_seen_at)}</span>
              {latestReadAt ? (
                <>
                  <span className="ws-meter-detail-sub-sep" aria-hidden>
                    ·
                  </span>
                  <span>Last read {formatWhen(latestReadAt)}</span>
                </>
              ) : null}
            </p>
          </div>
        </header>

        <nav
          className="ws-meter-detail-tabs"
          aria-label="Meter sections"
          role="tablist"
        >
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              id={`meter-tab-${t.id}`}
              className={`ws-meter-detail-tab${tab === t.id ? " is-active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="ws-meter-detail-panel">
          {tab === "summary" ? (
            <div className="ws-meter-detail-sections">
              <section
                className="ws-meter-detail-section ws-meter-detail-section--group"
                aria-labelledby="meter-identity-h"
              >
                <h2 id="meter-identity-h" className="ws-meter-detail-section-title">
                  Identity
                </h2>
                <dl className="ws-meter-detail-dl">
                  <DetailField label="Serial" value={detail.serial_number} mono />
                  <DetailField label="Meter ID" value={<span title={detail.id}>{detail.id}</span>} mono />
                  <DetailField
                    label="Utility #"
                    value={detail.utility_meter_number ?? "—"}
                    mono
                  />
                  <DetailField label="Badge" value={detail.badge_number ?? "—"} mono />
                  <DetailField label="Manufacturer" value={detail.manufacturer_code} />
                  <DetailField label="Model" value={detail.meter_model_code} />
                </dl>
              </section>

              <section
                className="ws-meter-detail-section ws-meter-detail-section--group"
                aria-labelledby="meter-registry-h"
              >
                <h2 id="meter-registry-h" className="ws-meter-detail-section-title">
                  Registry
                </h2>
                <dl className="ws-meter-detail-dl">
                  <DetailField
                    label="Firmware"
                    value={detail.firmware_version ?? "—"}
                    mono
                  />
                  <DetailField
                    label="Communication profile"
                    value={detail.communication_profile_code ?? "—"}
                    mono
                  />
                  <DetailField
                    label="Meter profile"
                    value={detail.meter_profile_code ?? "—"}
                    mono
                  />
                  <DetailField
                    label="Lifecycle"
                    value={humanizeEnum(detail.current_status)}
                  />
                  <DetailField
                    label="Active in registry"
                    value={detail.is_active ? "Yes" : "No"}
                  />
                  <DetailField label="Installed" value={formatWhen(detail.installed_at)} />
                  <DetailField label="Commissioned" value={formatWhen(detail.commissioned_at)} />
                  <DetailField label="Notes" value={detail.notes?.trim() ? detail.notes : "—"} />
                </dl>
                {detail.metadata_json && Object.keys(detail.metadata_json).length > 0 ? (
                  <pre className="ws-meter-detail-meta-json">
                    {JSON.stringify(detail.metadata_json, null, 2)}
                  </pre>
                ) : null}
              </section>

              <section
                className="ws-meter-detail-section ws-meter-detail-section--group"
                aria-labelledby="meter-connectivity-summary-h"
              >
                <h2 id="meter-connectivity-summary-h" className="ws-meter-detail-section-title">
                  Connectivity
                </h2>
                <dl className="ws-meter-detail-dl ws-meter-detail-dl--compact">
                  <DetailField label="Last seen" value={formatWhen(detail.last_seen_at)} />
                  <DetailField
                    label="Reachability"
                    value={
                      reachBucket === "online"
                        ? "Online (within 24h)"
                        : reachBucket === "offline"
                          ? "Stale (no recent check-in)"
                          : "Unknown"
                    }
                  />
                  <DetailField
                    label="Communication profile"
                    value={detail.communication_profile_code ?? "—"}
                    mono
                  />
                </dl>
              </section>

              <section
                className="ws-meter-detail-section ws-meter-detail-section--group"
                aria-labelledby="meter-asset-h"
              >
                <h2 id="meter-asset-h" className="ws-meter-detail-section-title">
                  Asset / linkage
                </h2>
                <dl className="ws-meter-detail-dl">
                  <DetailField
                    label="Service point"
                    value={
                      detail.service_point_id ? (
                        <span title={detail.service_point_id}>
                          {shortId(detail.service_point_id)}
                        </span>
                      ) : (
                        "—"
                      )
                    }
                    mono
                  />
                  <DetailField
                    label="Transformer"
                    value={
                      detail.transformer_id ? (
                        <span title={detail.transformer_id}>
                          {shortId(detail.transformer_id)}
                        </span>
                      ) : (
                        "—"
                      )
                    }
                    mono
                  />
                </dl>
              </section>

              <section className="ws-meter-detail-section" aria-labelledby="meter-lifecycle-h">
                <h2 id="meter-lifecycle-h" className="ws-meter-detail-section-title">
                  Lifecycle history
                </h2>
                {detail.status_history.length === 0 ? (
                  <p className="ws-muted">No status changes recorded.</p>
                ) : (
                  <div className="ws-meter-detail-table-wrap">
                    <table className="ws-meter-detail-table">
                      <thead>
                        <tr>
                          <th scope="col">When</th>
                          <th scope="col">From</th>
                          <th scope="col">To</th>
                          <th scope="col">Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.status_history.slice(0, 25).map((row) => (
                          <tr key={row.id}>
                            <td className="ws-meter-detail-nowrap">{formatWhen(row.changed_at)}</td>
                            <td>
                              {row.previous_status
                                ? humanizeEnum(row.previous_status)
                                : "—"}
                            </td>
                            <td>{humanizeEnum(row.new_status)}</td>
                            <td className="ws-muted">{row.reason?.trim() ? row.reason : "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </div>
          ) : null}

          {tab === "connectivity" ? (
            <div className="ws-meter-detail-sections">
              <section className="ws-meter-detail-section" aria-labelledby="conn-overview-h">
                <h2 id="conn-overview-h" className="ws-meter-detail-section-title">
                  Signal overview
                </h2>
                <dl className="ws-meter-detail-dl ws-meter-detail-dl--compact">
                  <DetailField label="Last seen" value={formatWhen(detail.last_seen_at)} />
                  <DetailField
                    label="Reachability"
                    value={
                      reachBucket === "online"
                        ? "Online (within 24h)"
                        : reachBucket === "offline"
                          ? "Offline (no recent check-in)"
                          : "Unknown"
                    }
                  />
                  <DetailField
                    label="Communication profile"
                    value={detail.communication_profile_code ?? "—"}
                    mono
                  />
                </dl>
              </section>

              <section className="ws-meter-detail-section" aria-labelledby="conn-endpoints-h">
                <h2 id="conn-endpoints-h" className="ws-meter-detail-section-title">
                  Endpoint assignments
                </h2>
                {assignments.state === "loading" || assignments.state === "idle" ? (
                  <p className="ws-muted">Loading…</p>
                ) : assignments.state === "err" ? (
                  <p className="ws-muted">{assignments.message}</p>
                ) : assignments.data.items.length === 0 ? (
                  <p className="ws-muted">No endpoint assignments.</p>
                ) : (
                  <div className="ws-meter-detail-table-wrap">
                    <table className="ws-meter-detail-table">
                      <thead>
                        <tr>
                          <th scope="col">Endpoint</th>
                          <th scope="col">Status</th>
                          <th scope="col">Primary</th>
                          <th scope="col">Assigned</th>
                        </tr>
                      </thead>
                      <tbody>
                        {assignments.data.items.map((row: MeterEndpointAssignmentListResponse["items"][number]) => (
                          <tr key={row.id}>
                            <td>
                              <span className="ws-meter-detail-strong">{row.endpoint_code}</span>
                              <span className="ws-muted"> — {row.endpoint_display_name}</span>
                            </td>
                            <td>{humanizeEnum(row.assignment_status)}</td>
                            <td>{row.is_primary ? "Yes" : "—"}</td>
                            <td className="ws-meter-detail-nowrap">{formatWhen(row.assigned_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className="ws-meter-detail-section" aria-labelledby="conn-sessions-h">
                <h2 id="conn-sessions-h" className="ws-meter-detail-section-title">
                  Recent sessions
                </h2>
                {sessions.state === "loading" || sessions.state === "idle" ? (
                  <p className="ws-muted">Loading…</p>
                ) : sessions.state === "err" ? (
                  <p className="ws-muted">{sessions.message}</p>
                ) : sessions.data.items.length === 0 ? (
                  <p className="ws-muted">No session history.</p>
                ) : (
                  <div className="ws-meter-detail-table-wrap">
                    <table className="ws-meter-detail-table">
                      <thead>
                        <tr>
                          <th scope="col">Started</th>
                          <th scope="col">Purpose</th>
                          <th scope="col">Status</th>
                          <th scope="col">Ended</th>
                          <th scope="col">Error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sessions.data.items.map((row: ConnectivitySessionHistoryListResponse["items"][number]) => (
                          <tr key={row.id}>
                            <td className="ws-meter-detail-nowrap">{formatWhen(row.started_at)}</td>
                            <td>{humanizeEnum(row.session_purpose)}</td>
                            <td>{humanizeEnum(row.status)}</td>
                            <td className="ws-meter-detail-nowrap">
                              {row.ended_at ? formatWhen(row.ended_at) : "—"}
                            </td>
                            <td className="ws-muted">
                              {row.error_code ?? row.error_message ?? "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </div>
          ) : null}

          {tab === "readings" ? (
            <section className="ws-meter-detail-section" aria-labelledby="readings-h">
              <h2 id="readings-h" className="ws-meter-detail-section-title">
                Captured readings
              </h2>
              {readings.state === "loading" || readings.state === "idle" ? (
                <p className="ws-muted">Loading…</p>
              ) : readings.state === "err" ? (
                <p className="ws-muted">{readings.message}</p>
              ) : readings.data.items.length === 0 ? (
                <p className="ws-muted">No readings for this meter.</p>
              ) : (
                <div className="ws-meter-detail-table-wrap">
                  <table className="ws-meter-detail-table">
                    <thead>
                      <tr>
                        <th scope="col">Captured</th>
                        <th scope="col">OBIS</th>
                        <th scope="col">Type</th>
                        <th scope="col">Value</th>
                        <th scope="col">Unit</th>
                        <th scope="col">Quality</th>
                      </tr>
                    </thead>
                    <tbody>
                      {readings.data.items.map((row: MeterReadingListResponse["items"][number]) => (
                        <tr key={row.id}>
                          <td className="ws-meter-detail-nowrap">{formatWhen(row.captured_at)}</td>
                          <td className="ws-meter-detail-mono">{row.obis_code}</td>
                          <td>{humanizeEnum(row.reading_type)}</td>
                          <td className="ws-meter-detail-mono">
                            {row.value_numeric ?? row.value_text ?? "—"}
                          </td>
                          <td>{row.unit ?? "—"}</td>
                          <td className="ws-muted">
                            {row.quality ? humanizeEnum(row.quality) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ) : null}

          {tab === "commands" ? (
            <section className="ws-meter-detail-section" aria-labelledby="commands-h">
              <h2 id="commands-h" className="ws-meter-detail-section-title">
                Recent commands
              </h2>
              {commands.state === "loading" || commands.state === "idle" ? (
                <p className="ws-muted">Loading…</p>
              ) : commands.state === "err" ? (
                <p className="ws-muted">{commands.message}</p>
              ) : commands.data.items.length === 0 ? (
                <p className="ws-muted">No command activity for this meter.</p>
              ) : (
                <div className="ws-meter-detail-table-wrap">
                  <table className="ws-meter-detail-table">
                    <thead>
                      <tr>
                        <th scope="col">Template</th>
                        <th scope="col">Family</th>
                        <th scope="col">Command</th>
                        <th scope="col">Approval</th>
                        <th scope="col">Attempt</th>
                        <th scope="col">Created</th>
                        <th scope="col">Updated</th>
                      </tr>
                    </thead>
                    <tbody>
                      {commands.data.items.map(
                        (row: MeterScopedCommandOperationalRecentListResponse["items"][number]) => (
                          <tr key={row.command_id}>
                            <td className="ws-meter-detail-strong">{row.command_template_code}</td>
                            <td>{humanizeEnum(row.command_family)}</td>
                            <td>{humanizeEnum(row.command_status)}</td>
                            <td>{humanizeEnum(row.approval_status)}</td>
                            <td className="ws-muted">
                              {row.latest_command_execution_attempt_status
                                ? humanizeEnum(row.latest_command_execution_attempt_status)
                                : "—"}
                            </td>
                            <td className="ws-meter-detail-nowrap">{formatWhen(row.created_at)}</td>
                            <td className="ws-meter-detail-nowrap">{formatWhen(row.latest_updated_at)}</td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ) : null}

          {tab === "audit" ? (
            <section className="ws-meter-detail-section" aria-labelledby="audit-h">
              <h2 id="audit-h" className="ws-meter-detail-section-title">
                Audit trail
              </h2>
              {audit.state === "loading" || audit.state === "idle" ? (
                <p className="ws-muted">Loading…</p>
              ) : audit.state === "err" ? (
                <p className="ws-muted">{audit.message}</p>
              ) : audit.data.items.length === 0 ? (
                <p className="ws-muted">No audit entries for this meter.</p>
              ) : (
                <div className="ws-meter-detail-table-wrap">
                  <table className="ws-meter-detail-table">
                    <thead>
                      <tr>
                        <th scope="col">When</th>
                        <th scope="col">Actor</th>
                        <th scope="col">Action</th>
                        <th scope="col">Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {audit.data.items.map((row: AuditLogListResponse["items"][number]) => (
                        <tr key={row.id}>
                          <td className="ws-meter-detail-nowrap">{formatWhen(row.created_at)}</td>
                          <td>{row.actor_username ?? "—"}</td>
                          <td className="ws-meter-detail-mono">{row.action}</td>
                          <td className="ws-muted">{row.description ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ) : null}

          {tab === "consumer" ? (
            <section className="ws-meter-detail-section" aria-labelledby="consumer-h">
              <h2 id="consumer-h" className="ws-meter-detail-section-title">
                Consumer linkage
              </h2>
              {linkage.state === "loading" || linkage.state === "idle" ? (
                <p className="ws-muted">Loading…</p>
              ) : linkage.state === "err" ? (
                <p className="ws-muted">{linkage.message}</p>
              ) : (
                <dl className="ws-meter-detail-dl">
                  <DetailField
                    label="Status"
                    value={humanizeEnum(linkage.data.linkage_status)}
                  />
                  <DetailField
                    label="Source"
                    value={
                      linkage.data.linkage_source
                        ? humanizeEnum(linkage.data.linkage_source)
                        : "—"
                    }
                  />
                  <DetailField
                    label="Consumer"
                    value={linkage.data.consumer_display_name ?? "—"}
                  />
                  <DetailField
                    label="Type"
                    value={
                      linkage.data.consumer_type
                        ? humanizeEnum(linkage.data.consumer_type)
                        : "—"
                    }
                  />
                  <DetailField
                    label="Account"
                    value={linkage.data.account_number ?? "—"}
                    mono
                  />
                  <DetailField
                    label="Service point"
                    value={linkage.data.service_point_code ?? "—"}
                    mono
                  />
                </dl>
              )}
            </section>
          ) : null}

          {tab === "gis" ? (
            <section className="ws-meter-detail-section" aria-labelledby="gis-h">
              <h2 id="gis-h" className="ws-meter-detail-section-title">
                GIS context
              </h2>
              {gis.state === "loading" || gis.state === "idle" ? (
                <p className="ws-muted">Loading…</p>
              ) : gis.state === "err" ? (
                <p className="ws-muted">{gis.message}</p>
              ) : gis.data.items.length === 0 ? (
                <p className="ws-muted">No GIS-lite row for this meter.</p>
              ) : (
                <div className="ws-meter-detail-gis-list">
                  {gis.data.items.map((row: GisLiteEntityListResponse["items"][number], i: number) => (
                    <dl
                      key={`${row.meter_id}-${i}`}
                      className="ws-meter-detail-dl ws-meter-detail-dl--gis"
                    >
                      <DetailField
                        label="Coordinates"
                        value={
                          row.has_coordinates && row.latitude != null && row.longitude != null
                            ? `${row.latitude.toFixed(5)}, ${row.longitude.toFixed(5)}`
                            : "—"
                        }
                        mono
                      />
                      <DetailField label="Address" value={row.address_line ?? "—"} />
                      <DetailField
                        label="Service point"
                        value={row.service_point_code ?? "—"}
                        mono
                      />
                      <DetailField
                        label="Last seen (GIS)"
                        value={formatWhen(row.meter_last_seen_at)}
                      />
                    </dl>
                  ))}
                </div>
              )}
            </section>
          ) : null}
        </div>
      </div>
  );
}
