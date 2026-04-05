"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { classifyReachabilityFromLastSeen } from "../dashboard/dashboard-utils";
import { REGISTRY_PAGE_LIMITS, RegistryPager } from "../registry-pagination";
import {
  MeterRegistryDrawer,
  type MeterRegistryRow,
  type RegistryDrawerMode,
} from "./meter-registry-drawer";
import { useSession } from "../session-provider";
import { WorkspaceShell } from "../workspace-shell";

const ROW_MENU_MIN_WIDTH_PX = 176;
const ROW_MENU_VIEWPORT_PAD = 8;

type MeterRow = {
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
  service_point_id: string | null;
  transformer_id: string | null;
  last_seen_at: string | null;
  is_active: boolean;
  notes: string | null;
};

type MeterListResponse = { total: number; items: MeterRow[] };

type GisEntity = {
  meter_id: string;
  has_coordinates: boolean;
};

type GisListResponse = { total: number; items: GisEntity[] };

type ReachBucket = ReturnType<typeof classifyReachabilityFromLastSeen>;

function serialLinkClassForReach(bucket: ReachBucket): string {
  if (bucket === "online") {
    return "ws-meters-serial-link ws-meters-serial-link--online";
  }
  if (bucket === "offline") {
    return "ws-meters-serial-link ws-meters-serial-link--offline";
  }
  return "ws-meters-serial-link ws-meters-serial-link--unknown";
}

function tonePositiveGreen(n: number) {
  return n > 0 ? "success" : "muted";
}

function tonePositiveRed(n: number) {
  return n > 0 ? "danger" : "muted";
}

function tonePositiveAmber(n: number) {
  return n > 0 ? "warning" : "muted";
}

function shortId(id: string): string {
  return `${id.slice(0, 8)}…`;
}

function formatShortDate(iso: string | null): string {
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

function toRegistryRow(m: MeterRow): MeterRegistryRow {
  return {
    id: m.id,
    serial_number: m.serial_number,
    utility_meter_number: m.utility_meter_number,
    badge_number: m.badge_number,
    manufacturer_id: m.manufacturer_id,
    manufacturer_code: m.manufacturer_code,
    meter_model_id: m.meter_model_id,
    meter_model_code: m.meter_model_code,
    firmware_version_id: m.firmware_version_id,
    firmware_version: m.firmware_version,
    communication_profile_id: m.communication_profile_id,
    communication_profile_code: m.communication_profile_code,
    meter_profile_id: m.meter_profile_id,
    meter_profile_code: m.meter_profile_code,
    current_status: m.current_status,
    notes: m.notes,
    is_active: m.is_active,
  };
}

function lifecycleChipTone(status: string): "success" | "info" | "muted" {
  if (status === "active") {
    return "success";
  }
  if (status === "registered" || status === "commissioned") {
    return "info";
  }
  return "muted";
}

function reachChipTone(bucket: ReachBucket): "success" | "danger" | "muted" {
  if (bucket === "online") {
    return "success";
  }
  if (bucket === "offline") {
    return "danger";
  }
  return "muted";
}

function humanizeReach(bucket: ReachBucket): string {
  if (bucket === "online") {
    return "Online";
  }
  if (bucket === "offline") {
    return "Offline";
  }
  return "Unknown";
}

const LIFECYCLE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All statuses" },
  { value: "registered", label: "Registered" },
  { value: "commissioned", label: "Commissioned" },
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
  { value: "retired", label: "Retired" },
];

const REACH_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All reachability" },
  { value: "online", label: "Online" },
  { value: "offline", label: "Offline" },
  { value: "unknown", label: "Unknown" },
];

const GIS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All mapping" },
  { value: "mapped", label: "GIS mapped" },
  { value: "unmapped", label: "Not mapped" },
];

type SummaryKpiProps = {
  label: string;
  value: string | number;
  accent: "neutral" | "success" | "danger" | "warning" | "info" | "muted";
};

function SummaryKpi({ label, value, accent }: SummaryKpiProps) {
  return (
    <div className={`ws-kpi ws-kpi--accent-${accent}`} aria-label={label}>
      <div className="ws-kpi-label">{label}</div>
      <div className="ws-kpi-value">{value}</div>
    </div>
  );
}

export function MetersRegistryClient() {
  return (
    <WorkspaceShell>
      <MetersRegistryBody />
    </WorkspaceShell>
  );
}

function MetersRegistryBody() {
  const { currentUser, isCheckingSession, authorizedFetch } = useSession();
  const [searchDraft, setSearchDraft] = useState("");
  const [searchApplied, setSearchApplied] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [reachFilter, setReachFilter] = useState("");
  const [gisFilter, setGisFilter] = useState("");
  const [limit, setLimit] = useState<(typeof REGISTRY_PAGE_LIMITS)[number]>(25);
  const [offset, setOffset] = useState(0);
  const [list, setList] = useState<MeterListResponse | null>(null);
  const [gisByMeterId, setGisByMeterId] = useState<Map<string, boolean>>(new Map());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [asOf, setAsOf] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<RegistryDrawerMode>("create");
  const [drawerMeter, setDrawerMeter] = useState<MeterRegistryRow | null>(null);
  const [rowMenu, setRowMenu] = useState<{
    top: number;
    left: number;
    meter: MeterRow;
  } | null>(null);
  const [portalReady, setPortalReady] = useState(false);

  useEffect(() => {
    setPortalReady(true);
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    if (searchApplied.trim()) {
      params.set("search", searchApplied.trim());
    }
    try {
      const [metersRes, gisRes] = await Promise.all([
        authorizedFetch<MeterListResponse>(`/api/v1/meters?${params.toString()}`),
        authorizedFetch<GisListResponse>("/api/v1/gis-lite/entities?limit=200").catch(() => ({
          total: 0,
          items: [] as GisEntity[],
        })),
      ]);
      setList(metersRes);
      const gisMap = new Map<string, boolean>();
      for (const row of gisRes.items) {
        gisMap.set(row.meter_id, row.has_coordinates);
      }
      setGisByMeterId(gisMap);
      setAsOf(new Date().toISOString());
    } catch (e) {
      setList(null);
      setGisByMeterId(new Map());
      setError(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }, [authorizedFetch, limit, offset, searchApplied]);

  const openDrawer = (mode: RegistryDrawerMode, meter: MeterRegistryRow | null) => {
    setDrawerMode(mode);
    setDrawerMeter(meter);
    setDrawerOpen(true);
    setRowMenu(null);
  };

  const toggleRowMenu = (meter: MeterRow, triggerEl: HTMLElement) => {
    if (rowMenu?.meter.id === meter.id) {
      setRowMenu(null);
      return;
    }
    const rect = triggerEl.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const left = Math.min(
      Math.max(ROW_MENU_VIEWPORT_PAD, rect.right - ROW_MENU_MIN_WIDTH_PX),
      vw - ROW_MENU_MIN_WIDTH_PX - ROW_MENU_VIEWPORT_PAD,
    );
    const top = Math.min(rect.bottom + 4, vh - ROW_MENU_VIEWPORT_PAD);
    setRowMenu({ top, left, meter });
  };

  useEffect(() => {
    if (!rowMenu) {
      return;
    }
    const onDocMouseDown = (ev: MouseEvent) => {
      const t = ev.target as HTMLElement | null;
      if (!t) {
        return;
      }
      if (t.closest(".ws-row-actions-popover")) {
        return;
      }
      if (t.closest(".ws-row-actions-trigger")) {
        return;
      }
      setRowMenu(null);
    };
    const onKeyDown = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") {
        setRowMenu(null);
      }
    };
    const onViewportChange = () => setRowMenu(null);
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("scroll", onViewportChange, true);
    window.addEventListener("resize", onViewportChange);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", onViewportChange, true);
      window.removeEventListener("resize", onViewportChange);
    };
  }, [rowMenu]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }
    void fetchData();
  }, [currentUser, fetchData]);

  useEffect(() => {
    const t = window.setTimeout(() => setSearchApplied(searchDraft), 400);
    return () => window.clearTimeout(t);
  }, [searchDraft]);

  const nowMs = Date.now();

  const displayed = useMemo(() => {
    if (!list) {
      return [];
    }
    return list.items.filter((m) => {
      if (statusFilter && m.current_status !== statusFilter) {
        return false;
      }
      if (reachFilter) {
        const b = classifyReachabilityFromLastSeen(m.last_seen_at, nowMs);
        if (b !== reachFilter) {
          return false;
        }
      }
      if (gisFilter) {
        const mapped = gisByMeterId.get(m.id);
        if (gisFilter === "mapped") {
          return mapped === true;
        }
        if (gisFilter === "unmapped") {
          return mapped !== true;
        }
      }
      return true;
    });
  }, [gisByMeterId, gisFilter, list, nowMs, reachFilter, statusFilter]);

  const summary = useMemo(() => {
    let online = 0;
    let offline = 0;
    let unknown = 0;
    let gisMapped = 0;
    for (const m of displayed) {
      const b = classifyReachabilityFromLastSeen(m.last_seen_at, nowMs);
      if (b === "online") {
        online += 1;
      } else if (b === "offline") {
        offline += 1;
      } else {
        unknown += 1;
      }
      if (gisByMeterId.get(m.id) === true) {
        gisMapped += 1;
      }
    }
    return { online, offline, unknown, gisMapped };
  }, [displayed, gisByMeterId, nowMs]);

  const hasClientFilters = Boolean(statusFilter || reachFilter || gisFilter);
  const totalForStrip = list
    ? hasClientFilters
      ? displayed.length
      : list.total
    : null;

  const clearFilters = () => {
    setSearchDraft("");
    setSearchApplied("");
    setStatusFilter("");
    setReachFilter("");
    setGisFilter("");
    setOffset(0);
  };

  const canPrev = offset > 0;
  const canNext = list ? offset + limit < list.total : false;

  if (isCheckingSession) {
    return <p className="ws-muted">Checking session…</p>;
  }

  if (!currentUser) {
    return (
      <div className="ws-canvas ws-canvas--gate">
        <p className="ws-muted">Sign in to view meters.</p>
        <Link href="/login" className="ws-btn ws-btn-primary">
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="ws-meters-page">
      <header className="ws-meters-header">
        <div>
          <h1 className="ws-page-title">Meters</h1>
          <p className="ws-page-subtitle">Inventory and operational registry.</p>
        </div>
        <div className="ws-meters-header-right">
          {asOf ? (
            <p className="ws-dash-asof ws-meters-asof">
              Updated {formatShortDate(asOf)}
            </p>
          ) : null}
        </div>
      </header>

      {error ? (
        <p className="ws-dash-banner" role="alert">
          {error}
        </p>
      ) : null}

      {loading && !list ? <p className="ws-dash-loading">Loading…</p> : null}

      {list ? (
        <>
          <section className="ws-meters-summary" aria-label="Summary">
            <div className="ws-kpi-grid ws-meters-summary-grid">
              <SummaryKpi
                label="Total"
                value={totalForStrip ?? "—"}
                accent="neutral"
              />
              <SummaryKpi
                label="Online"
                value={summary.online}
                accent={tonePositiveGreen(summary.online)}
              />
              <SummaryKpi
                label="Offline"
                value={summary.offline}
                accent={tonePositiveRed(summary.offline)}
              />
              <SummaryKpi
                label="Intermittent / unknown"
                value={summary.unknown}
                accent={tonePositiveAmber(summary.unknown)}
              />
              <SummaryKpi
                label="GIS mapped"
                value={summary.gisMapped}
                accent={summary.gisMapped > 0 ? "info" : "muted"}
              />
            </div>
          </section>

          <div className="ws-meters-toolbar" role="search">
            <div className="ws-meters-toolbar-filters">
              <label className="ws-meters-search">
                <span className="ws-meters-toolbar-label">Search</span>
                <input
                  type="search"
                  value={searchDraft}
                  onChange={(ev) => {
                    setSearchDraft(ev.target.value);
                    setOffset(0);
                  }}
                  placeholder="Serial, utility #, badge…"
                  autoComplete="off"
                />
              </label>
              <label className="ws-meters-filter">
                <span className="ws-meters-toolbar-label">Lifecycle</span>
                <select
                  value={statusFilter}
                  onChange={(ev) => {
                    setStatusFilter(ev.target.value);
                    setOffset(0);
                  }}
                >
                  {LIFECYCLE_OPTIONS.map((o) => (
                    <option key={o.value || "all"} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="ws-meters-filter">
                <span className="ws-meters-toolbar-label">Reachability</span>
                <select
                  value={reachFilter}
                  onChange={(ev) => {
                    setReachFilter(ev.target.value);
                    setOffset(0);
                  }}
                >
                  {REACH_OPTIONS.map((o) => (
                    <option key={o.value || "all-r"} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="ws-meters-filter">
                <span className="ws-meters-toolbar-label">GIS</span>
                <select
                  value={gisFilter}
                  onChange={(ev) => {
                    setGisFilter(ev.target.value);
                    setOffset(0);
                  }}
                >
                  {GIS_OPTIONS.map((o) => (
                    <option key={o.value || "all-g"} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              {(searchDraft || statusFilter || reachFilter || gisFilter) ? (
                <button type="button" className="ws-btn ws-btn-ghost ws-meters-clear" onClick={clearFilters}>
                  Clear
                </button>
              ) : null}
            </div>
            <div className="ws-meters-toolbar-registry">
              <button
                type="button"
                className="ws-btn ws-btn-secondary ws-meters-add"
                onClick={() => openDrawer("create", null)}
              >
                Add meter
              </button>
            </div>
          </div>

          <div className="ws-meters-table-wrap">
            <table className="ws-meters-table">
              <thead>
                <tr>
                  <th scope="col">Serial</th>
                  <th scope="col">Utility #</th>
                  <th scope="col">Manufacturer</th>
                  <th scope="col">Model</th>
                  <th scope="col">Comm profile</th>
                  <th scope="col">Meter profile</th>
                  <th scope="col">Firmware</th>
                  <th scope="col">Lifecycle</th>
                  <th scope="col">Last seen</th>
                  <th scope="col">Reachability</th>
                  <th scope="col" className="ws-meters-col-narrow">
                    Svc pt
                  </th>
                  <th scope="col" className="ws-meters-col-narrow">
                    Xfmr
                  </th>
                  <th scope="col">GIS</th>
                  <th scope="col" className="ws-meters-th-actions">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {displayed.length === 0 ? (
                  <tr>
                    <td colSpan={14} className="ws-meters-table-empty">
                      {list.items.length === 0
                        ? "No meters found."
                        : "No matching meters."}
                    </td>
                  </tr>
                ) : (
                  displayed.map((m) => {
                    const bucket = classifyReachabilityFromLastSeen(m.last_seen_at, nowMs);
                    const gisMapped = gisByMeterId.get(m.id) === true;
                    const gisLabel = gisByMeterId.has(m.id)
                      ? gisMapped
                        ? "Mapped"
                        : "Unlocated"
                      : "—";
                    return (
                      <tr key={m.id}>
                        <td className="ws-meters-mono">
                          <Link
                            className={serialLinkClassForReach(bucket)}
                            href={`/meters/${m.id}`}
                            title={`Open meter ${m.serial_number}`}
                          >
                            {m.serial_number}
                          </Link>
                        </td>
                        <td className="ws-meters-mono">{m.utility_meter_number ?? "—"}</td>
                        <td>{m.manufacturer_code}</td>
                        <td>{m.meter_model_code}</td>
                        <td className="ws-meters-mono">{m.communication_profile_code ?? "—"}</td>
                        <td className="ws-meters-mono">{m.meter_profile_code ?? "—"}</td>
                        <td className="ws-meters-mono">{m.firmware_version ?? "—"}</td>
                        <td>
                          <span className={`ws-chip ws-chip--${lifecycleChipTone(m.current_status)}`}>
                            {humanizeStatus(m.current_status)}
                          </span>
                        </td>
                        <td className="ws-meters-nowrap">{formatShortDate(m.last_seen_at)}</td>
                        <td>
                          <span className={`ws-chip ws-chip--${reachChipTone(bucket)}`}>
                            {humanizeReach(bucket)}
                          </span>
                        </td>
                        <td className="ws-meters-mono ws-meters-col-narrow">
                          {m.service_point_id ? shortId(m.service_point_id) : "—"}
                        </td>
                        <td className="ws-meters-mono ws-meters-col-narrow">
                          {m.transformer_id ? shortId(m.transformer_id) : "—"}
                        </td>
                        <td>
                          <span
                            className={`ws-chip ws-chip--${
                              !gisByMeterId.has(m.id)
                                ? "muted"
                                : gisMapped
                                  ? "success"
                                  : "muted"
                            }`}
                          >
                            {gisLabel}
                          </span>
                        </td>
                        <td className="ws-meters-actions">
                          <div className="ws-row-actions">
                            <button
                              type="button"
                              className="ws-row-actions-trigger"
                              aria-expanded={rowMenu?.meter.id === m.id}
                              aria-haspopup="menu"
                              aria-label="Registry actions"
                              onClick={(ev) => toggleRowMenu(m, ev.currentTarget)}
                            >
                              ⋯
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <RegistryPager
            disabled={loading}
            pageSize={limit}
            onPageSizeChange={(n) => {
              setLimit(n as (typeof REGISTRY_PAGE_LIMITS)[number]);
              setOffset(0);
            }}
            rangeStart={list.total === 0 ? 0 : offset + 1}
            rangeEnd={list.total === 0 ? 0 : offset + list.items.length}
            total={list.total}
            entityLabel="meters"
            canPrev={canPrev}
            canNext={canNext}
            onPrev={() => setOffset((o) => Math.max(0, o - limit))}
            onNext={() => setOffset((o) => o + limit)}
          />
        </>
      ) : null}

      {portalReady && rowMenu
        ? createPortal(
            <ul
              className="ws-row-actions-menu ws-row-actions-popover"
              role="menu"
              style={{ top: rowMenu.top, left: rowMenu.left }}
            >
              <li role="none">
                <button
                  type="button"
                  role="menuitem"
                  className="ws-row-actions-item"
                  onClick={() => openDrawer("edit", toRegistryRow(rowMenu.meter))}
                >
                  Edit registry
                </button>
              </li>
              <li role="none">
                <button
                  type="button"
                  role="menuitem"
                  className="ws-row-actions-item"
                  onClick={() => openDrawer("lifecycle", toRegistryRow(rowMenu.meter))}
                >
                  Change lifecycle
                </button>
              </li>
              <li role="none">
                <button
                  type="button"
                  role="menuitem"
                  className="ws-row-actions-item ws-row-actions-item--secondary"
                  onClick={() => openDrawer("toggle-active", toRegistryRow(rowMenu.meter))}
                >
                  {rowMenu.meter.is_active ? "Set inactive" : "Set active"}
                </button>
              </li>
            </ul>,
            document.body,
          )
        : null}

      <MeterRegistryDrawer
        open={drawerOpen}
        mode={drawerMode}
        meter={drawerMeter}
        onClose={() => {
          setDrawerOpen(false);
          setDrawerMeter(null);
        }}
        onSuccess={() => void fetchData()}
        authorizedFetch={authorizedFetch}
      />
    </div>
  );
}
