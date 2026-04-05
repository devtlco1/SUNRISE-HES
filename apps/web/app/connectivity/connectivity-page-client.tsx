"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { aggregateReachabilityFromGisEntities, classifyReachabilityFromLastSeen } from "../dashboard/dashboard-utils";
import { useSession } from "../session-provider";
import { WorkspaceShell } from "../workspace-shell";

const GIS_WINDOW_LIMIT = 200;
const RECENT_ACTIVITY_ROWS = 8;

type GisEntityRow = {
  meter_id: string;
  meter_serial_number: string;
  meter_status: string;
  meter_last_seen_at: string | null;
  service_point_code: string | null;
  has_coordinates: boolean;
  location_presence: string;
};

type GisListResponse = { total: number; items: GisEntityRow[] };
type MeterHeadResponse = { total: number };
type EndpointListResponse = { total: number };

type ReachBucket = ReturnType<typeof classifyReachabilityFromLastSeen>;

type AttentionScope = "attention" | "offline" | "unknown" | "all";

type KpiAccent = "neutral" | "success" | "danger" | "warning" | "info" | "muted";

function fmt(n: number | null): string {
  if (n === null || Number.isNaN(n)) {
    return "—";
  }
  return n.toLocaleString("en-US");
}

function fmtAsOf(iso: string | null): string {
  if (!iso) {
    return "";
  }
  try {
    return new Date(iso).toLocaleString("en-US", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function formatShortWhen(iso: string | null): string {
  if (!iso) {
    return "—";
  }
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function humanizeStatus(s: string): string {
  return s.replace(/_/g, " ");
}

function reachLabel(bucket: ReachBucket): string {
  if (bucket === "online") {
    return "Online";
  }
  if (bucket === "offline") {
    return "Offline";
  }
  return "Unknown";
}

function serialLinkClass(bucket: ReachBucket): string {
  if (bucket === "online") {
    return "ws-meters-serial-link ws-meters-serial-link--online";
  }
  if (bucket === "offline") {
    return "ws-meters-serial-link ws-meters-serial-link--offline";
  }
  return "ws-meters-serial-link ws-meters-serial-link--unknown";
}

function reachMetricClass(bucket: ReachBucket): string {
  if (bucket === "online") {
    return "ws-metric ws-metric--success";
  }
  if (bucket === "offline") {
    return "ws-metric ws-metric--danger";
  }
  return "ws-metric ws-metric--muted";
}

function tonePositiveGreen(n: number): KpiAccent {
  return n > 0 ? "success" : "muted";
}

function tonePositiveRed(n: number): KpiAccent {
  return n > 0 ? "danger" : "muted";
}

function tonePositiveMuted(n: number): KpiAccent {
  return n > 0 ? "muted" : "muted";
}

function tonePositiveBlue(n: number | null): KpiAccent {
  if (n === null || n <= 0) {
    return "muted";
  }
  return "info";
}

type SummaryKpiProps = {
  label: string;
  value: string;
  accent: KpiAccent;
};

function SummaryKpi({ label, value, accent }: SummaryKpiProps) {
  return (
    <div className={`ws-kpi ws-kpi--accent-${accent}`} aria-label={label}>
      <div className="ws-kpi-label">{label}</div>
      <div className="ws-kpi-value">{value}</div>
    </div>
  );
}

export function ConnectivityPageClient() {
  return (
    <WorkspaceShell>
      <ConnectivityBody />
    </WorkspaceShell>
  );
}

function ConnectivityBody() {
  const { currentUser, isCheckingSession, authorizedFetch } = useSession();
  const [asOf, setAsOf] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [metersTotal, setMetersTotal] = useState<number | null>(null);
  const [gisItems, setGisItems] = useState<GisEntityRow[]>([]);
  const [endpointsTotal, setEndpointsTotal] = useState<number | null>(null);

  const [searchDraft, setSearchDraft] = useState("");
  const [searchApplied, setSearchApplied] = useState("");
  const [attentionScope, setAttentionScope] = useState<AttentionScope>("attention");
  const [lifecycleFilter, setLifecycleFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setErrors([]);
    const nextErrors: string[] = [];
    const stamp = new Date().toISOString();
    setAsOf(stamp);

    const settled = await Promise.allSettled([
      authorizedFetch<MeterHeadResponse>(`/api/v1/meters?limit=1&offset=0`),
      authorizedFetch<GisListResponse>(`/api/v1/gis-lite/entities?limit=${GIS_WINDOW_LIMIT}`),
      authorizedFetch<EndpointListResponse>("/api/v1/communication-endpoints"),
    ]);

    if (settled[0].status === "fulfilled") {
      setMetersTotal(settled[0].value.total);
    } else {
      setMetersTotal(null);
      nextErrors.push(
        `Meters: ${settled[0].reason instanceof Error ? settled[0].reason.message : String(settled[0].reason)}`,
      );
    }

    if (settled[1].status === "fulfilled") {
      setGisItems(settled[1].value.items);
    } else {
      setGisItems([]);
      nextErrors.push(
        `GIS-lite: ${settled[1].reason instanceof Error ? settled[1].reason.message : String(settled[1].reason)}`,
      );
    }

    if (settled[2].status === "fulfilled") {
      setEndpointsTotal(settled[2].value.total);
    } else {
      setEndpointsTotal(null);
      nextErrors.push(
        `Endpoints: ${settled[2].reason instanceof Error ? settled[2].reason.message : String(settled[2].reason)}`,
      );
    }

    setErrors(nextErrors);
    setLoading(false);
  }, [authorizedFetch]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }
    void load();
  }, [currentUser, load]);

  useEffect(() => {
    const t = window.setTimeout(() => setSearchApplied(searchDraft), 350);
    return () => window.clearTimeout(t);
  }, [searchDraft]);

  const nowMs = Date.now();

  const buckets = useMemo(() => {
    if (gisItems.length === 0) {
      return { online: 0, offline: 0, unknown: 0, sampleSize: 0 };
    }
    return aggregateReachabilityFromGisEntities(gisItems, nowMs);
  }, [gisItems, nowMs]);

  const lifecycleOptions = useMemo(() => {
    const u = new Set<string>();
    for (const row of gisItems) {
      u.add(row.meter_status);
    }
    return Array.from(u).sort((a, b) => a.localeCompare(b));
  }, [gisItems]);

  const recentActivity = useMemo(() => {
    const onlineRows = gisItems.filter(
      (r) => classifyReachabilityFromLastSeen(r.meter_last_seen_at, nowMs) === "online",
    );
    return onlineRows
      .filter((r) => r.meter_last_seen_at)
      .sort((a, b) => Date.parse(b.meter_last_seen_at!) - Date.parse(a.meter_last_seen_at!))
      .slice(0, RECENT_ACTIVITY_ROWS);
  }, [gisItems, nowMs]);

  const attentionRows = useMemo(() => {
    const q = searchApplied.trim().toLowerCase();
    return gisItems.filter((row) => {
      if (lifecycleFilter && row.meter_status !== lifecycleFilter) {
        return false;
      }
      if (q && !row.meter_serial_number.toLowerCase().includes(q)) {
        return false;
      }
      const b = classifyReachabilityFromLastSeen(row.meter_last_seen_at, nowMs);
      if (attentionScope === "attention") {
        return b === "offline" || b === "unknown";
      }
      if (attentionScope === "offline") {
        return b === "offline";
      }
      if (attentionScope === "unknown") {
        return b === "unknown";
      }
      return true;
    });
  }, [attentionScope, gisItems, lifecycleFilter, nowMs, searchApplied]);

  if (isCheckingSession) {
    return <p className="ws-muted">Checking session…</p>;
  }

  if (!currentUser) {
    return <p className="ws-muted">Sign in to view connectivity.</p>;
  }

  return (
    <div className="ws-canvas ws-conn-page">
      <header className="ws-conn-header">
        <div>
          <h1 className="ws-conn-title">Connectivity</h1>
          <p className="ws-conn-subtitle">Fleet reachability and meters to review.</p>
        </div>
        {asOf ? <p className="ws-muted ws-conn-asof">As of {fmtAsOf(asOf)}</p> : null}
      </header>

      {errors.length > 0 ? (
        <div className="ws-conn-errors" role="alert">
          {errors.map((e) => (
            <p key={e} className="ws-alert">
              {e}
            </p>
          ))}
        </div>
      ) : null}

      <section className="ws-conn-summary" aria-label="Connectivity summary">
        <div className="ws-kpi-grid ws-conn-kpi-grid ws-conn-kpi-grid--five">
          <SummaryKpi label="Online" value={fmt(buckets.sampleSize ? buckets.online : null)} accent={tonePositiveGreen(buckets.online)} />
          <SummaryKpi label="Offline" value={fmt(buckets.sampleSize ? buckets.offline : null)} accent={tonePositiveRed(buckets.offline)} />
          <SummaryKpi
            label="Unknown / not seen"
            value={fmt(buckets.sampleSize ? buckets.unknown : null)}
            accent={tonePositiveMuted(buckets.unknown)}
          />
          <SummaryKpi label="Fleet meters" value={fmt(metersTotal)} accent="neutral" />
          <SummaryKpi label="Comm endpoints" value={fmt(endpointsTotal)} accent={tonePositiveBlue(endpointsTotal)} />
        </div>
      </section>

      <div className="ws-conn-stack">
        <section
          className="ws-dash-panel ws-conn-panel ws-conn-attention-primary"
          aria-labelledby="conn-attention-h"
        >
          <h2 className="ws-dash-panel-title" id="conn-attention-h">
            Meters needing attention
          </h2>
          <div className="ws-dash-panel-body ws-conn-attention-body">
            <div className="ws-conn-toolbar">
              <div className="ws-conn-toolbar-filters">
                <label className="ws-conn-field">
                  <span className="ws-conn-field-label">Search</span>
                  <input
                    type="search"
                    value={searchDraft}
                    onChange={(e) => setSearchDraft(e.target.value)}
                    placeholder="Serial…"
                    autoComplete="off"
                  />
                </label>
                <label className="ws-conn-field">
                  <span className="ws-conn-field-label">Reachability</span>
                  <select
                    value={attentionScope}
                    onChange={(e) => setAttentionScope(e.target.value as AttentionScope)}
                    aria-label="Reachability filter"
                  >
                    <option value="attention">Offline or unknown</option>
                    <option value="offline">Offline only</option>
                    <option value="unknown">Unknown only</option>
                    <option value="all">All</option>
                  </select>
                </label>
                <label className="ws-conn-field">
                  <span className="ws-conn-field-label">Lifecycle</span>
                  <select
                    value={lifecycleFilter}
                    onChange={(e) => setLifecycleFilter(e.target.value)}
                    aria-label="Lifecycle filter"
                  >
                    <option value="">All</option>
                    {lifecycleOptions.map((s) => (
                      <option key={s} value={s}>
                        {humanizeStatus(s)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <button type="button" className="ws-btn ws-btn-ghost ws-conn-refresh" onClick={() => void load()} disabled={loading}>
                Refresh
              </button>
            </div>

            {loading && gisItems.length === 0 ? (
              <p className="ws-muted">Loading…</p>
            ) : gisItems.length === 0 && !loading ? (
              <p className="ws-muted">Data not available yet.</p>
            ) : (
              <div className="ws-conn-table-wrap">
                <table className="ws-conn-table">
                  <thead>
                    <tr>
                      <th scope="col">Serial</th>
                      <th scope="col">Reachability</th>
                      <th scope="col">Last seen</th>
                      <th scope="col">Lifecycle</th>
                      <th scope="col">Service point</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attentionRows.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="ws-conn-table-empty">
                          {attentionScope === "attention" ? "No meters need attention." : "No matching meters."}
                        </td>
                      </tr>
                    ) : (
                      attentionRows.map((row) => {
                        const b = classifyReachabilityFromLastSeen(row.meter_last_seen_at, nowMs);
                        return (
                          <tr key={row.meter_id}>
                            <td>
                              <Link className={serialLinkClass(b)} href={`/meters/${row.meter_id}`}>
                                {row.meter_serial_number}
                              </Link>
                            </td>
                            <td>
                              <span className={reachMetricClass(b)}>{reachLabel(b)}</span>
                            </td>
                            <td className="ws-conn-mono">{formatShortWhen(row.meter_last_seen_at)}</td>
                            <td>{humanizeStatus(row.meter_status)}</td>
                            <td>{row.service_point_code ?? "—"}</td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        <section className="ws-dash-panel ws-conn-panel ws-conn-support" aria-labelledby="conn-activity-h">
          <h2 className="ws-dash-panel-title" id="conn-activity-h">
            Recent activity
          </h2>
          <div className="ws-dash-panel-body ws-conn-support-body">
            {gisItems.length === 0 && !loading ? (
              <p className="ws-muted">Data not available yet.</p>
            ) : recentActivity.length === 0 ? (
              <p className="ws-muted">No recent activity.</p>
            ) : (
              <div className="ws-conn-table-wrap">
                <table className="ws-conn-table ws-conn-table--compact">
                  <thead>
                    <tr>
                      <th scope="col">Serial</th>
                      <th scope="col">Last seen</th>
                      <th scope="col">Service point</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentActivity.map((row) => (
                      <tr key={row.meter_id}>
                        <td>
                          <Link className={serialLinkClass("online")} href={`/meters/${row.meter_id}`}>
                            {row.meter_serial_number}
                          </Link>
                        </td>
                        <td className="ws-conn-mono">{formatShortWhen(row.meter_last_seen_at)}</td>
                        <td>{row.service_point_code ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
