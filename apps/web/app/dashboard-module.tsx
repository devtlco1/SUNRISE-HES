"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  DataTableShell,
  StatCard,
  StatusChip,
  SummaryList,
  SurfaceCard,
  formatDateTime,
  formatStatusLabel,
  getStatusTone,
  type StatusTone,
} from "./operational-ui";
import type { AuthorizedFetch } from "./operational-shell";
import { FourCircleIcon, PieChartIcon, TableIcon, UserIcon } from "./nextadmin-icons";

type MeterListItem = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  manufacturer_code: string;
  meter_model_code: string;
  communication_profile_code: string | null;
  meter_profile_code: string | null;
  firmware_version: string | null;
  current_status: string;
  transformer_id: string | null;
  service_point_id: string | null;
  last_seen_at: string | null;
  is_active: boolean;
};

type MeterListResponse = {
  total: number;
  items: MeterListItem[];
};

type CommandRecentItem = {
  command_id: string;
  command_family: string;
  command_status: string;
  meter_id: string;
  command_template_code: string;
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

type MeterReadingItem = {
  id: string;
  captured_at: string;
  quality?: string | null;
};

type MeterReadingListResponse = {
  total: number;
  items: MeterReadingItem[];
};

type GisLiteEntity = {
  meter_id: string;
  meter_status: string;
  meter_last_seen_at: string | null;
  service_point_id: string | null;
  service_point_code: string | null;
  has_coordinates: boolean;
  subscriber_display_name: string | null;
  account_number: string | null;
  location_presence: "coordinates_available" | "service_point_only" | "unlinked";
};

type GisLiteEntityListResponse = {
  total: number;
  items: GisLiteEntity[];
};

type DeskSnapshot = {
  totalMeters: number;
  visibleMeters: MeterListItem[];
  recentCommands: CommandRecentItem[];
  pendingApprovals: CommandRecentItem[];
  recentEvents: RecentEventItem[];
  recentSessionsByMeterId: Record<string, ConnectivitySession | null>;
  recentReadingsByMeterId: Record<string, MeterReadingItem | null>;
  gisByMeterId: Record<string, GisLiteEntity | null>;
};

type AttentionItem = {
  id: string;
  label: string;
  count: number;
  detail: string;
  href: string;
  cta: string;
  tone: StatusTone;
};

const STALE_MS = 1000 * 60 * 60 * 24;

function outcomeLine(summary: Record<string, string | null>): string {
  if ("terminal_status_category" in summary) {
    return summary.terminal_status_category ?? "—";
  }
  if ("relay_control_operation" in summary) {
    const op = summary.relay_control_operation ?? "relay";
    const out = summary.relay_control_execution_outcome ?? "pending";
    return `${op} · ${out}`;
  }
  if ("on_demand_read_operation" in summary) {
    const op = summary.on_demand_read_operation ?? "read";
    const snap = summary.snapshot_type ?? "snapshot";
    const out = summary.on_demand_read_execution_outcome ?? "pending";
    return `${op} ${snap} · ${out}`;
  }
  return "—";
}

function ageShort(iso: string | null): string {
  if (!iso) {
    return "No last signal";
  }
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) {
    return formatDateTime(iso);
  }
  const h = Math.floor((Date.now() - t) / (1000 * 60 * 60));
  if (h < 1) {
    return "<1h";
  }
  if (h < 24) {
    return `${h}h`;
  }
  return `${Math.floor(h / 24)}d`;
}

function signalBadge(
  lastSeenAt: string | null,
  session: ConnectivitySession | null,
): { label: string; tone: StatusTone } {
  if (!lastSeenAt) {
    return { label: "No comms", tone: "danger" };
  }
  const t = new Date(lastSeenAt).getTime();
  if (Number.isNaN(t)) {
    return { label: "Unknown", tone: "neutral" };
  }
  if (session && ["failed", "timed_out", "cancelled"].includes(session.status)) {
    return { label: "Degraded", tone: "warning" };
  }
  if (Date.now() - t >= STALE_MS) {
    return { label: "Stale", tone: "warning" };
  }
  return { label: "Live", tone: "positive" };
}

export function DashboardModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [desk, setDesk] = useState<DeskSnapshot | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [partialError, setPartialError] = useState(false);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    setPartialError(false);

    try {
      const [metersR, cmdR, apprR, evtR] = await Promise.allSettled([
        authorizedFetch<MeterListResponse>("/api/v1/meters?offset=0&limit=20"),
        authorizedFetch<CommandRecentListResponse>("/api/v1/commands/recent?limit=12"),
        authorizedFetch<CommandRecentListResponse>("/api/v1/commands/approvals/pending?limit=20"),
        authorizedFetch<RecentEventListResponse>("/api/v1/events/recent?limit=20"),
      ]);

      if (metersR.status !== "fulfilled") {
        throw metersR.reason instanceof Error ? metersR.reason : new Error("Meter scope failed.");
      }

      const visible = metersR.value.items;
      const [sessR, readR, gisR] = await Promise.all([
        Promise.allSettled(
          visible.map((m) =>
            authorizedFetch<ConnectivitySessionHistoryListResponse>(
              `/api/v1/meters/${m.id}/sessions?limit=1`,
            ),
          ),
        ),
        Promise.allSettled(
          visible.map((m) =>
            authorizedFetch<MeterReadingListResponse>(`/api/v1/meters/${m.id}/readings?limit=1`),
          ),
        ),
        Promise.allSettled(
          visible.map((m) =>
            authorizedFetch<GisLiteEntityListResponse>(
              `/api/v1/gis-lite/entities?limit=1&meter_id=${m.id}`,
            ),
          ),
        ),
      ]);

      const recentSessionsByMeterId: Record<string, ConnectivitySession | null> = {};
      const recentReadingsByMeterId: Record<string, MeterReadingItem | null> = {};
      const gisByMeterId: Record<string, GisLiteEntity | null> = {};

      visible.forEach((m, i) => {
        recentSessionsByMeterId[m.id] =
          sessR[i]?.status === "fulfilled" ? sessR[i].value.items[0] ?? null : null;
        recentReadingsByMeterId[m.id] =
          readR[i]?.status === "fulfilled" ? readR[i].value.items[0] ?? null : null;
        gisByMeterId[m.id] =
          gisR[i]?.status === "fulfilled" ? gisR[i].value.items[0] ?? null : null;
      });

      setDesk({
        totalMeters: metersR.value.total,
        visibleMeters: visible,
        recentCommands: cmdR.status === "fulfilled" ? cmdR.value.items : [],
        pendingApprovals: apprR.status === "fulfilled" ? apprR.value.items : [],
        recentEvents: evtR.status === "fulfilled" ? evtR.value.items : [],
        recentSessionsByMeterId,
        recentReadingsByMeterId,
        gisByMeterId,
      });

      const anyFail = [cmdR, apprR, evtR, ...sessR, ...readR, ...gisR].some(
        (r) => r.status === "rejected",
      );
      setPartialError(anyFail);
    } catch (e) {
      setDesk(null);
      setLoadError(e instanceof Error ? e.message : "Load failed.");
    } finally {
      setLoading(false);
    }
  }, [authorizedFetch]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const serialByMeterId = useMemo(() => {
    if (!desk) {
      return {} as Record<string, string>;
    }
    return Object.fromEntries(desk.visibleMeters.map((m) => [m.id, m.serial_number]));
  }, [desk]);

  const kpis = useMemo(() => {
    if (!desk) {
      return [];
    }
    const sigs = desk.visibleMeters.map((m) =>
      signalBadge(m.last_seen_at, desk.recentSessionsByMeterId[m.id] ?? null),
    );
    const live = sigs.filter((s) => s.label === "Live").length;
    const offline = desk.visibleMeters.filter((m) => !m.last_seen_at).length;
    const warn = sigs.filter((s) => s.tone === "warning").length;
    const severe = desk.recentEvents.filter((e) =>
      ["critical", "major"].includes(e.severity.toLowerCase()),
    ).length;
    const withRead = Object.values(desk.recentReadingsByMeterId).filter(Boolean).length;
    const withoutRead = desk.visibleMeters.length - withRead;
    const plotted = Object.values(desk.gisByMeterId).filter((g) => g?.has_coordinates).length;

    return [
      {
        label: "Registered endpoints",
        value: String(desk.totalMeters),
        note: `Sample: ${desk.visibleMeters.length} meters`,
        tone: "neutral" as const,
        icon: TableIcon,
      },
      {
        label: "Live signal (sample)",
        value: String(live),
        note: `${offline} no comms · ${warn} stale/degraded`,
        tone: live > 0 ? ("positive" as const) : ("warning" as const),
        icon: PieChartIcon,
      },
      {
        label: "Approval backlog",
        value: String(desk.pendingApprovals.length),
        note: "Gated remote actions",
        tone: desk.pendingApprovals.length > 0 ? ("warning" as const) : ("neutral" as const),
        icon: FourCircleIcon,
      },
      {
        label: "Severe events (feed)",
        value: String(severe),
        note: `${desk.recentEvents.length} rows in recent feed`,
        tone: severe > 0 ? ("danger" as const) : ("info" as const),
        icon: UserIcon,
      },
      {
        label: "Read coverage (sample)",
        value: String(withRead),
        note: `${withoutRead} without latest read`,
        tone: "info" as const,
        icon: PieChartIcon,
      },
      {
        label: "Plotted assets (sample)",
        value: String(plotted),
        note: "Meters with coordinates in sample",
        tone: plotted > 0 ? ("positive" as const) : ("warning" as const),
        icon: TableIcon,
      },
    ];
  }, [desk]);

  const networkRow = useMemo(() => {
    if (!desk) {
      return null;
    }
    const sigs = desk.visibleMeters.map((m) =>
      signalBadge(m.last_seen_at, desk.recentSessionsByMeterId[m.id] ?? null),
    );
    return {
      live: sigs.filter((s) => s.label === "Live").length,
      dark: desk.visibleMeters.filter((m) => !m.last_seen_at).length,
      risk: sigs.filter((s) => s.tone === "warning").length,
      exceptions: desk.visibleMeters
        .map((m) => ({
          m,
          s: signalBadge(m.last_seen_at, desk.recentSessionsByMeterId[m.id] ?? null),
          session: desk.recentSessionsByMeterId[m.id] ?? null,
        }))
        .filter((x) => x.s.tone !== "positive")
        .slice(0, 4),
    };
  }, [desk]);

  const readRow = useMemo(() => {
    if (!desk) {
      return null;
    }
    const vals = Object.values(desk.recentReadingsByMeterId);
    return {
      ok: vals.filter(Boolean).length,
      gap: vals.filter((v) => !v).length,
      suspect: vals.filter(
        (v) => v && v.quality && !["actual", "valid"].includes(String(v.quality)),
      ).length,
    };
  }, [desk]);

  const gisRow = useMemo(() => {
    if (!desk) {
      return null;
    }
    const vals = Object.values(desk.gisByMeterId);
    return {
      coords: vals.filter((g) => g?.has_coordinates).length,
      spOnly: vals.filter((g) => g?.location_presence === "service_point_only").length,
      orphan: vals.filter((g) => g?.location_presence === "unlinked").length,
      billed: vals.filter((g) => g?.account_number).length,
    };
  }, [desk]);

  const cmdPosture = useMemo(() => {
    if (!desk) {
      return null;
    }
    const c = desk.recentCommands;
    return {
      queue: c.filter((x) => x.command_status.toLowerCase().includes("queue")).length,
      fail: c.filter((x) => ["failed", "timed_out", "cancelled"].includes(x.command_status)).length,
      ok: c.filter(
        (x) =>
          x.command_status.toLowerCase().includes("succeed") ||
          x.command_status.toLowerCase().includes("complete"),
      ).length,
      approvals: desk.pendingApprovals.length,
    };
  }, [desk]);

  const alarmPosture = useMemo(() => {
    if (!desk) {
      return null;
    }
    const e = desk.recentEvents;
    return {
      crit: e.filter((x) => x.severity === "critical").length,
      maj: e.filter((x) => x.severity === "major").length,
      low: e.filter((x) => ["warning", "minor"].includes(x.severity)).length,
      open: e.filter((x) => ["new", "acknowledged", "in_investigation"].includes(x.event_state))
        .length,
    };
  }, [desk]);

  const attention = useMemo<AttentionItem[]>(() => {
    if (!desk || !networkRow || !readRow) {
      return [];
    }
    const out: AttentionItem[] = [];
    if (desk.pendingApprovals.length > 0) {
      out.push({
        id: "appr",
        label: "Approval backlog",
        count: desk.pendingApprovals.length,
        detail: "Remote actions awaiting sign-off.",
        href: "/commands?tab=approvals",
        cta: "Open approvals",
        tone: "warning",
      });
    }
    if (networkRow.dark > 0 || networkRow.risk > 0) {
      out.push({
        id: "net",
        label: "Network exceptions",
        count: networkRow.dark + networkRow.risk,
        detail: "No comms, stale, or degraded sessions in sample.",
        href: "/connectivity",
        cta: "Connectivity",
        tone: "danger",
      });
    }
    if (readRow.gap > 0) {
      out.push({
        id: "read",
        label: "Read gaps",
        count: readRow.gap,
        detail: "Endpoints in sample missing a latest read.",
        href: "/readings",
        cta: "Readings",
        tone: "warning",
      });
    }
    const sev = desk.recentEvents.filter((x) =>
      ["critical", "major"].includes(x.severity.toLowerCase()),
    ).length;
    if (sev > 0) {
      out.push({
        id: "evt",
        label: "Severe events",
        count: sev,
        detail: "Critical or major rows in the recent feed.",
        href: "/jobs-events-alerts",
        cta: "Monitoring",
        tone: "danger",
      });
    }
    return out.slice(0, 5);
  }, [desk, networkRow, readRow]);

  if (loading && !desk) {
    return (
      <div className="hes-op-dash-root">
        <div className="hes-op-dash-kpis">
          {["Registered endpoints", "Live signal (sample)", "Approval backlog", "Severe events"].map(
            (label) => (
              <StatCard key={label} label={label} note="Loading…" tone="neutral" value="…" />
            ),
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="hes-op-dash-root">
      {loadError ? <p className="error-banner">{loadError}</p> : null}
      {partialError ? (
        <p className="error-banner">Partial data: supporting requests failed for some panels.</p>
      ) : null}

      <nav className="hes-op-dash-shortcuts" aria-label="Operational shortcuts">
        <Link href="/meters">Meters</Link>
        <span aria-hidden="true">·</span>
        <Link href="/connectivity">Connectivity</Link>
        <span aria-hidden="true">·</span>
        <Link href="/commands">Commands</Link>
        <span aria-hidden="true">·</span>
        <Link href="/readings">Readings</Link>
        <span aria-hidden="true">·</span>
        <Link href="/jobs-events-alerts">Monitoring</Link>
        <span aria-hidden="true">·</span>
        <Link href="/gis-lite">GIS Lite</Link>
      </nav>

      <div className="hes-op-dash-kpis">
        {kpis.map((k) => (
          <StatCard
            key={k.label}
            icon={k.icon}
            label={k.label}
            note={k.note}
            tone={k.tone}
            value={k.value}
          />
        ))}
      </div>

      <div className="hes-op-dash-triple">
        <SurfaceCard
          title="Network posture"
          description="Communications state for the loaded meter sample."
          aside={<Link className="secondary-button" href="/connectivity">Connectivity</Link>}
        >
          {networkRow ? (
            <>
              <SummaryList
                items={[
                  { label: "Live", value: String(networkRow.live), tone: "positive" },
                  { label: "No comms", value: String(networkRow.dark), tone: "danger" },
                  { label: "Stale / degraded", value: String(networkRow.risk), tone: "warning" },
                ]}
              />
              <div className="hes-queue-list hes-op-dash-tight-list">
                {networkRow.exceptions.length === 0 ? (
                  <p className="muted">No exceptions in sample.</p>
                ) : (
                  networkRow.exceptions.map(({ m, s, session }) => (
                    <article key={m.id} className="hes-queue-item">
                      <div>
                        <Link className="hes-mono" href={`/meters/${m.id}`}>
                          {m.serial_number}
                        </Link>
                        <p>
                          {session
                            ? `${formatStatusLabel(session.status)} · ${formatStatusLabel(session.session_purpose)}`
                            : "No session"}{" "}
                          · {ageShort(m.last_seen_at)}
                        </p>
                      </div>
                      <StatusChip label={s.label} tone={s.tone} />
                    </article>
                  ))
                )}
              </div>
            </>
          ) : (
            <p className="muted">Unavailable.</p>
          )}
        </SurfaceCard>

        <SurfaceCard
          title="Read pipeline"
          description="Latest interval capture in the sample."
          aside={<Link className="secondary-button" href="/readings">Readings</Link>}
        >
          {readRow ? (
            <SummaryList
              items={[
                { label: "With latest read", value: String(readRow.ok), tone: "positive" },
                { label: "Missing read", value: String(readRow.gap), tone: readRow.gap > 0 ? "warning" : "neutral" },
                {
                  label: "Non-standard quality",
                  value: String(readRow.suspect),
                  tone: readRow.suspect > 0 ? "danger" : "neutral",
                },
              ]}
            />
          ) : (
            <p className="muted">Unavailable.</p>
          )}
        </SurfaceCard>

        <SurfaceCard
          title="Location linkage"
          description="GIS footprint for the sample."
          aside={<Link className="secondary-button" href="/gis-lite">GIS Lite</Link>}
        >
          {gisRow ? (
            <SummaryList
              items={[
                { label: "Coordinates", value: String(gisRow.coords), tone: "positive" },
                { label: "Service point only", value: String(gisRow.spOnly), tone: gisRow.spOnly > 0 ? "warning" : "neutral" },
                { label: "Unlinked", value: String(gisRow.orphan), tone: gisRow.orphan > 0 ? "danger" : "neutral" },
                { label: "Account linked", value: String(gisRow.billed), tone: "info" },
              ]}
            />
          ) : (
            <p className="muted">Unavailable.</p>
          )}
        </SurfaceCard>
      </div>

      <div className="hes-op-dash-main-split">
        <div className="hes-op-dash-primary">
          <SurfaceCard title="Triage queue" description="Highest-impact follow-ups from this desk.">
            <div className="hes-queue-list hes-op-dash-tight-list">
              {attention.length === 0 ? (
                <p className="muted">No open triage items from current signals.</p>
              ) : (
                attention.map((a) => (
                  <article key={a.id} className="hes-queue-item">
                    <div>
                      <strong>{a.label}</strong>
                      <p>{a.detail}</p>
                    </div>
                    <div className="hes-queue-item-actions">
                      <StatusChip label={String(a.count)} tone={a.tone} />
                      <Link className="secondary-button" href={a.href}>
                        {a.cta}
                      </Link>
                    </div>
                  </article>
                ))
              )}
            </div>
          </SurfaceCard>

          <DataTableShell
            title="Remote action log"
            description="Latest commands in scope (newest first)."
            aside={<Link className="secondary-button" href="/commands">Commands</Link>}
          >
            {desk?.recentCommands.length ? (
              <table className="hes-data-table hes-op-dash-cmd-table">
                <thead>
                  <tr>
                    <th>Meter</th>
                    <th>Template</th>
                    <th>Status</th>
                    <th>Outcome</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {desk.recentCommands.map((cmd) => (
                    <tr key={cmd.command_id}>
                      <td>
                        <div className="hes-table-identity">
                          <Link href={`/meters/${cmd.meter_id}`}>
                            <strong>{serialByMeterId[cmd.meter_id] ?? cmd.meter_id}</strong>
                          </Link>
                          <span className="hes-mono">{cmd.meter_id}</span>
                        </div>
                      </td>
                      <td>
                        <strong>{cmd.command_template_code}</strong>
                      </td>
                      <td>
                        <StatusChip
                          label={formatStatusLabel(cmd.command_status)}
                          tone={getStatusTone(cmd.command_status)}
                        />
                      </td>
                      <td>{outcomeLine(cmd.family_specific_outcome_summary)}</td>
                      <td>{formatDateTime(cmd.latest_updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="hes-empty-copy">No command rows.</p>
            )}
          </DataTableShell>
        </div>

        <div className="hes-op-dash-secondary">
          <SurfaceCard
            title="Event roll-up"
            description="Recent alarm feed, condensed."
            aside={<Link className="secondary-button" href="/jobs-events-alerts">Monitoring</Link>}
          >
            {alarmPosture ? (
              <>
                <SummaryList
                  items={[
                    { label: "Critical", value: String(alarmPosture.crit), tone: alarmPosture.crit > 0 ? "danger" : "neutral" },
                    { label: "Major", value: String(alarmPosture.maj), tone: alarmPosture.maj > 0 ? "warning" : "neutral" },
                    { label: "Minor / warning", value: String(alarmPosture.low), tone: alarmPosture.low > 0 ? "info" : "neutral" },
                    { label: "Open workflow", value: String(alarmPosture.open), tone: alarmPosture.open > 0 ? "warning" : "neutral" },
                  ]}
                />
                <div className="hes-queue-list hes-op-dash-tight-list">
                  {desk?.recentEvents.slice(0, 5).map((ev) => (
                    <article key={ev.id} className="hes-queue-item">
                      <div>
                        <strong>{ev.event_name ?? ev.event_code}</strong>
                        <p>
                          {ev.meter_id ? (
                            <Link href={`/meters/${ev.meter_id}`}>
                              {serialByMeterId[ev.meter_id] ?? ev.meter_id}
                            </Link>
                          ) : (
                            "Unassigned"
                          )}{" "}
                          · {formatDateTime(ev.occurred_at)}
                        </p>
                      </div>
                      <StatusChip label={formatStatusLabel(ev.severity)} tone={getStatusTone(ev.severity)} />
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <p className="muted">Unavailable.</p>
            )}
          </SurfaceCard>

          <SurfaceCard title="Remote operations posture" description="Command queue health from recent activity.">
            {cmdPosture ? (
              <SummaryList
                items={[
                  { label: "Pending approvals", value: String(cmdPosture.approvals), tone: cmdPosture.approvals > 0 ? "warning" : "neutral" },
                  { label: "Queued", value: String(cmdPosture.queue), tone: cmdPosture.queue > 0 ? "warning" : "neutral" },
                  { label: "Succeeded", value: String(cmdPosture.ok), tone: "positive" },
                  { label: "Failed / abandoned", value: String(cmdPosture.fail), tone: cmdPosture.fail > 0 ? "danger" : "neutral" },
                ]}
              />
            ) : (
              <p className="muted">Unavailable.</p>
            )}
          </SurfaceCard>
        </div>
      </div>
    </div>
  );
}
