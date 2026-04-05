"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useSession } from "../session-provider";
import { WorkspaceShell } from "../workspace-shell";

const RECENT_LIMIT = 100;
const PENDING_LIMIT = 50;

type CommandOperationalRecentListItem = {
  command_id: string;
  command_family: string;
  command_category: string;
  command_status: string;
  approval_status: string;
  approval_reviewed_at: string | null;
  approval_notes: string | null;
  meter_id: string;
  command_template_code: string;
  latest_command_execution_attempt_id: string | null;
  latest_command_execution_attempt_status: string | null;
  runtime_execution_record_id: string | null;
  family_specific_outcome_summary: Record<string, unknown>;
  orchestration_artifact_present: boolean;
  terminalization_artifact_present: boolean;
  execute_now_artifact_present: boolean;
  created_at: string;
  latest_updated_at: string;
};

type CommandOperationalRecentListResponse = {
  total: number;
  limit: number;
  family_filter: string | null;
  approval_filter: string | null;
  items: CommandOperationalRecentListItem[];
};

type GisLiteRow = {
  meter_id: string;
  meter_serial_number: string;
};

type GisLiteListResponse = { total: number; items: GisLiteRow[] };

type KpiAccent = "neutral" | "success" | "danger" | "warning" | "info" | "muted";

function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

function shortId(id: string): string {
  return `${id.slice(0, 8)}…`;
}

function fmtWhen(iso: string | null): string {
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

function fmt(n: number): string {
  return n.toLocaleString("en-US");
}

function outcomePreview(summary: Record<string, unknown>): string {
  const keys = Object.keys(summary);
  if (keys.length === 0) {
    return "—";
  }
  try {
    const raw = JSON.stringify(summary);
    return raw.length > 96 ? `${raw.slice(0, 93)}…` : raw;
  } catch {
    return "—";
  }
}

function executionStatusAccent(status: string): KpiAccent {
  if (status === "succeeded") {
    return "success";
  }
  if (status === "failed" || status === "timed_out") {
    return "danger";
  }
  if (status === "in_progress" || status === "queued") {
    return "info";
  }
  if (status === "pending" || status === "scheduled" || status === "retry_wait") {
    return "warning";
  }
  if (status === "cancelled") {
    return "muted";
  }
  return "neutral";
}

function approvalAccent(status: string): KpiAccent {
  if (status === "submitted_for_approval") {
    return "warning";
  }
  if (status === "rejected") {
    return "danger";
  }
  if (status === "approved") {
    return "success";
  }
  return "muted";
}

type SummaryKpiProps = { label: string; value: string; accent: KpiAccent };

function SummaryKpi({ label, value, accent }: SummaryKpiProps) {
  return (
    <div className={`ws-kpi ws-kpi--accent-${accent}`} aria-label={label}>
      <div className="ws-kpi-label">{label}</div>
      <div className="ws-kpi-value">{value}</div>
    </div>
  );
}

function toneCount(n: number, pos: KpiAccent): KpiAccent {
  return n > 0 ? pos : "muted";
}

export function CommandsPageClient() {
  return (
    <WorkspaceShell>
      <CommandsBody />
    </WorkspaceShell>
  );
}

const FAMILY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All families" },
  { value: "profile_capture", label: "Profile capture" },
  { value: "relay_control", label: "Relay control" },
  { value: "on_demand_read", label: "On-demand read" },
];

const APPROVAL_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All approvals" },
  { value: "not_required", label: "Not required" },
  { value: "submitted_for_approval", label: "Submitted for approval" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

const EXEC_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All execution states" },
  { value: "pending", label: "Pending" },
  { value: "scheduled", label: "Scheduled" },
  { value: "queued", label: "Queued" },
  { value: "in_progress", label: "In progress" },
  { value: "retry_wait", label: "Retry wait" },
  { value: "succeeded", label: "Succeeded" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "timed_out", label: "Timed out" },
];

function CommandsBody() {
  const { currentUser, isCheckingSession, authorizedFetch } = useSession();
  const [asOf, setAsOf] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [recent, setRecent] = useState<CommandOperationalRecentListResponse | null>(null);
  const [pending, setPending] = useState<CommandOperationalRecentListResponse | null>(null);
  const [serialByMeterId, setSerialByMeterId] = useState<Map<string, string>>(new Map());

  const [familyApi, setFamilyApi] = useState("");
  const [approvalApi, setApprovalApi] = useState("");
  const [execClient, setExecClient] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [searchApplied, setSearchApplied] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setErrors([]);
    setAsOf(new Date().toISOString());
    const nextErrors: string[] = [];

    const recentParams = new URLSearchParams();
    recentParams.set("limit", String(RECENT_LIMIT));
    if (familyApi) {
      recentParams.set("family", familyApi);
    }
    if (approvalApi) {
      recentParams.set("approval", approvalApi);
    }

    const pendingParams = new URLSearchParams();
    pendingParams.set("limit", String(PENDING_LIMIT));

    const settled = await Promise.allSettled([
      authorizedFetch<CommandOperationalRecentListResponse>(`/api/v1/commands/recent?${recentParams}`),
      authorizedFetch<CommandOperationalRecentListResponse>(`/api/v1/commands/approvals/pending?${pendingParams}`),
      authorizedFetch<GisLiteListResponse>("/api/v1/gis-lite/entities?limit=200").catch(() => ({
        total: 0,
        items: [] as GisLiteRow[],
      })),
    ]);

    if (settled[0].status === "fulfilled") {
      setRecent(settled[0].value);
    } else {
      setRecent(null);
      nextErrors.push(
        `Commands recent: ${settled[0].reason instanceof Error ? settled[0].reason.message : String(settled[0].reason)}`,
      );
    }

    if (settled[1].status === "fulfilled") {
      setPending(settled[1].value);
    } else {
      setPending(null);
      nextErrors.push(
        `Approvals pending: ${settled[1].reason instanceof Error ? settled[1].reason.message : String(settled[1].reason)}`,
      );
    }

    if (settled[2].status === "fulfilled") {
      const m = new Map<string, string>();
      for (const row of settled[2].value.items) {
        m.set(row.meter_id, row.meter_serial_number);
      }
      setSerialByMeterId(m);
    } else {
      setSerialByMeterId(new Map());
    }

    setErrors(nextErrors);
    setLoading(false);
  }, [approvalApi, authorizedFetch, familyApi]);

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

  const recentItems = recent?.items ?? [];

  const kpi = useMemo(() => {
    const queuedInProgress = recentItems.filter((r) => r.command_status === "queued" || r.command_status === "in_progress")
      .length;
    const awaiting = recentItems.filter((r) =>
      ["pending", "scheduled", "retry_wait"].includes(r.command_status),
    ).length;
    const succeeded = recentItems.filter((r) => r.command_status === "succeeded").length;
    const failed = recentItems.filter((r) => r.command_status === "failed" || r.command_status === "timed_out").length;
    const pendingApprovalCount = pending?.items.length ?? 0;
    return {
      inWindow: recentItems.length,
      pendingApprovalCount,
      queuedInProgress,
      awaiting,
      succeeded,
      failed,
    };
  }, [pending?.items.length, recentItems]);

  const filteredTable = useMemo(() => {
    const q = searchApplied.trim().toLowerCase();
    return recentItems.filter((row) => {
      if (execClient && row.command_status !== execClient) {
        return false;
      }
      if (!q) {
        return true;
      }
      const serial = serialByMeterId.get(row.meter_id) ?? "";
      return (
        row.command_id.toLowerCase().includes(q) ||
        row.command_template_code.toLowerCase().includes(q) ||
        row.meter_id.toLowerCase().includes(q) ||
        serial.toLowerCase().includes(q)
      );
    });
  }, [execClient, recentItems, searchApplied, serialByMeterId]);

  const attentionRows = useMemo(() => {
    const rows: CommandOperationalRecentListItem[] = [];
    const seen = new Set<string>();
    for (const row of pending?.items ?? []) {
      if (!seen.has(row.command_id)) {
        seen.add(row.command_id);
        rows.push(row);
      }
    }
    for (const row of recentItems) {
      if (row.command_status === "failed" || row.command_status === "timed_out") {
        if (!seen.has(row.command_id)) {
          seen.add(row.command_id);
          rows.push(row);
        }
      }
    }
    return rows.slice(0, 18);
  }, [pending?.items, recentItems]);

  if (isCheckingSession) {
    return <p className="ws-muted">Checking session…</p>;
  }

  if (!currentUser) {
    return <p className="ws-muted">Sign in to view commands.</p>;
  }

  return (
    <div className="ws-canvas ws-cmd-page">
      <header className="ws-cmd-header">
        <div>
          <h1 className="ws-cmd-title">Commands</h1>
          <p className="ws-cmd-subtitle">Remote meter command submissions, approvals, and execution posture.</p>
        </div>
        {asOf ? <p className="ws-muted ws-cmd-asof">As of {fmtAsOf(asOf)}</p> : null}
      </header>

      {errors.length > 0 ? (
        <div className="ws-cmd-errors" role="alert">
          {errors.map((e) => (
            <p key={e} className="ws-alert">
              {e}
            </p>
          ))}
        </div>
      ) : null}

      <section className="ws-cmd-summary" aria-label="Commands summary">
        <div className="ws-kpi-grid ws-cmd-kpi-grid">
          <SummaryKpi label="Recent commands" value={recent ? fmt(kpi.inWindow) : "—"} accent="neutral" />
          <SummaryKpi
            label="Pending approval"
            value={pending ? fmt(kpi.pendingApprovalCount) : "—"}
            accent={toneCount(kpi.pendingApprovalCount, "warning")}
          />
          <SummaryKpi
            label="Queued / in progress"
            value={recent ? fmt(kpi.queuedInProgress) : "—"}
            accent={toneCount(kpi.queuedInProgress, "info")}
          />
          <SummaryKpi
            label="Awaiting response"
            value={recent ? fmt(kpi.awaiting) : "—"}
            accent={toneCount(kpi.awaiting, "warning")}
          />
          <SummaryKpi
            label="Succeeded"
            value={recent ? fmt(kpi.succeeded) : "—"}
            accent={toneCount(kpi.succeeded, "success")}
          />
          <SummaryKpi
            label="Failed / timed out"
            value={recent ? fmt(kpi.failed) : "—"}
            accent={toneCount(kpi.failed, "danger")}
          />
        </div>
      </section>

      <div className="ws-cmd-stack">
        <section className="ws-dash-panel ws-cmd-panel" aria-labelledby="cmd-overview-h">
          <h2 className="ws-dash-panel-title" id="cmd-overview-h">
            Command overview
          </h2>
          <div className="ws-dash-panel-body ws-cmd-overview-body">
            {!recent && !loading ? (
              <p className="ws-muted">Data not available yet.</p>
            ) : (
              <>
                <p className="ws-cmd-overview-lead">
                  Operational list shows up to <span className="ws-metric ws-metric--neutral">{RECENT_LIMIT}</span>{" "}
                  recent commands for supported families. Approval queue samples up to{" "}
                  <span className="ws-metric ws-metric--neutral">{PENDING_LIMIT}</span> pending reviews. KPI counts
                  reflect the loaded window only.
                </p>
                <dl className="ws-cmd-dl">
                  <div>
                    <dt>Pending approval (sample)</dt>
                    <dd>
                      <span className={`ws-metric ws-metric--${kpi.pendingApprovalCount > 0 ? "warning" : "muted"}`}>
                        {pending ? fmt(kpi.pendingApprovalCount) : "—"}
                      </span>
                    </dd>
                  </div>
                  <div>
                    <dt>Active execution</dt>
                    <dd>
                      <span className={`ws-metric ws-metric--${kpi.queuedInProgress > 0 ? "info" : "muted"}`}>
                        {recent ? fmt(kpi.queuedInProgress) : "—"}
                      </span>
                    </dd>
                  </div>
                  <div>
                    <dt>Terminal success</dt>
                    <dd>
                      <span className={`ws-metric ws-metric--${kpi.succeeded > 0 ? "success" : "muted"}`}>
                        {recent ? fmt(kpi.succeeded) : "—"}
                      </span>
                    </dd>
                  </div>
                  <div>
                    <dt>Terminal failure</dt>
                    <dd>
                      <span className={`ws-metric ws-metric--${kpi.failed > 0 ? "danger" : "muted"}`}>
                        {recent ? fmt(kpi.failed) : "—"}
                      </span>
                    </dd>
                  </div>
                </dl>
              </>
            )}
          </div>
        </section>

        <section className="ws-dash-panel ws-cmd-panel" aria-labelledby="cmd-registry-h">
          <h2 className="ws-dash-panel-title" id="cmd-registry-h">
            Command registry
          </h2>
          <div className="ws-dash-panel-body ws-cmd-registry-body">
            <div className="ws-cmd-toolbar">
              <div className="ws-cmd-toolbar-filters">
                <label className="ws-cmd-field">
                  <span className="ws-cmd-field-label">Family</span>
                  <select
                    value={familyApi}
                    onChange={(e) => setFamilyApi(e.target.value)}
                    aria-label="Command family filter"
                  >
                    {FAMILY_OPTIONS.map((o) => (
                      <option key={o.value || "all"} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-cmd-field">
                  <span className="ws-cmd-field-label">Approval</span>
                  <select
                    value={approvalApi}
                    onChange={(e) => setApprovalApi(e.target.value)}
                    aria-label="Approval filter"
                  >
                    {APPROVAL_OPTIONS.map((o) => (
                      <option key={o.value || "all-a"} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-cmd-field">
                  <span className="ws-cmd-field-label">Execution</span>
                  <select
                    value={execClient}
                    onChange={(e) => setExecClient(e.target.value)}
                    aria-label="Execution status filter"
                  >
                    {EXEC_OPTIONS.map((o) => (
                      <option key={o.value || "all-e"} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-cmd-field">
                  <span className="ws-cmd-field-label">Search</span>
                  <input
                    type="search"
                    value={searchDraft}
                    onChange={(e) => setSearchDraft(e.target.value)}
                    placeholder="Serial, command id, template…"
                    autoComplete="off"
                  />
                </label>
              </div>
              <button type="button" className="ws-btn ws-btn-ghost ws-cmd-refresh" onClick={() => void load()} disabled={loading}>
                Refresh
              </button>
            </div>

            {loading && recentItems.length === 0 ? (
              <p className="ws-muted">Loading…</p>
            ) : (
              <div className="ws-cmd-table-wrap">
                <table className="ws-cmd-table">
                  <thead>
                    <tr>
                      <th scope="col">Command</th>
                      <th scope="col">Type</th>
                      <th scope="col">Meter</th>
                      <th scope="col">Submitted</th>
                      <th scope="col">Approval</th>
                      <th scope="col">Execution</th>
                      <th scope="col">Attempt</th>
                      <th scope="col">Updated</th>
                      <th scope="col">Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTable.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="ws-cmd-table-empty">
                          No commands found.
                        </td>
                      </tr>
                    ) : (
                      filteredTable.map((row) => {
                        const serial = serialByMeterId.get(row.meter_id);
                        const meterLabel = serial ?? shortId(row.meter_id);
                        return (
                          <tr key={row.command_id}>
                            <td className="ws-cmd-mono">{shortId(row.command_id)}</td>
                            <td>{row.command_template_code}</td>
                            <td>
                              <Link className="ws-meters-drilldown" href={`/meters/${row.meter_id}`} title={row.meter_id}>
                                {meterLabel}
                              </Link>
                            </td>
                            <td className="ws-cmd-mono">{fmtWhen(row.created_at)}</td>
                            <td>
                              <span className={`ws-metric ws-metric--${approvalAccent(row.approval_status)}`}>
                                {humanize(row.approval_status)}
                              </span>
                            </td>
                            <td>
                              <span className={`ws-metric ws-metric--${executionStatusAccent(row.command_status)}`}>
                                {humanize(row.command_status)}
                              </span>
                            </td>
                            <td>
                              {row.latest_command_execution_attempt_status ? (
                                <span
                                  className={`ws-metric ws-metric--${executionStatusAccent(
                                    row.latest_command_execution_attempt_status,
                                  )}`}
                                >
                                  {humanize(row.latest_command_execution_attempt_status)}
                                </span>
                              ) : (
                                "—"
                              )}
                            </td>
                            <td className="ws-cmd-mono">{fmtWhen(row.latest_updated_at)}</td>
                            <td className="ws-cmd-outcome">{outcomePreview(row.family_specific_outcome_summary)}</td>
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

        <section className="ws-dash-panel ws-cmd-panel" aria-labelledby="cmd-attention-h">
          <h2 className="ws-dash-panel-title" id="cmd-attention-h">
            Attention
          </h2>
          <div className="ws-dash-panel-body">
            {attentionRows.length === 0 ? (
              <p className="ws-muted">No commands need attention.</p>
            ) : (
              <div className="ws-cmd-table-wrap">
                <table className="ws-cmd-table ws-cmd-table--compact">
                  <thead>
                    <tr>
                      <th scope="col">Command</th>
                      <th scope="col">Meter</th>
                      <th scope="col">Issue</th>
                      <th scope="col">Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attentionRows.map((row) => {
                      const serial = serialByMeterId.get(row.meter_id);
                      const meterLabel = serial ?? shortId(row.meter_id);
                      const issue =
                        row.approval_status === "submitted_for_approval"
                          ? "Pending approval"
                          : row.command_status === "failed"
                            ? "Execution failed"
                            : row.command_status === "timed_out"
                              ? "Timed out"
                              : "Needs review";
                      return (
                        <tr key={`att-${row.command_id}`}>
                          <td className="ws-cmd-mono">{shortId(row.command_id)}</td>
                          <td>
                            <Link className="ws-meters-drilldown" href={`/meters/${row.meter_id}`} title={row.meter_id}>
                              {meterLabel}
                            </Link>
                          </td>
                          <td>
                            <span
                              className={`ws-metric ws-metric--${
                                row.approval_status === "submitted_for_approval" ? "warning" : "danger"
                              }`}
                            >
                              {issue}
                            </span>
                          </td>
                          <td className="ws-cmd-mono">{fmtWhen(row.latest_updated_at)}</td>
                        </tr>
                      );
                    })}
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
