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

type CommandTemplate = {
  id: string;
  code: string;
  name: string;
  category: string;
  is_active: boolean;
};

type CommandTemplateListResponse = { total: number; items: CommandTemplate[] };

type BulkWizardResponse = {
  submitted_total: number;
  failed_total: number;
  items: Array<{
    meter_id: string;
    command_id: string | null;
    submission_status: string;
    detail: string | null;
  }>;
};

type KpiAccent = "neutral" | "success" | "danger" | "warning" | "info" | "muted";

type BulkFamily = "relay_control" | "on_demand_read";

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

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function parseMeterIds(text: string): string[] {
  const parts = text
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const seen = new Set<string>();
  const out: string[] = [];
  for (const p of parts) {
    if (!UUID_RE.test(p) || seen.has(p.toLowerCase())) {
      continue;
    }
    seen.add(p.toLowerCase());
    out.push(p);
  }
  return out;
}

function templatesForBulkFamily(family: BulkFamily, items: CommandTemplate[]): CommandTemplate[] {
  if (family === "relay_control") {
    return items.filter((t) => t.category === "remote_disconnect" || t.category === "remote_reconnect");
  }
  return items.filter((t) => t.category === "on_demand_read");
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

  const [bulkOpen, setBulkOpen] = useState(false);
  const [templates, setTemplates] = useState<CommandTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [bulkFamily, setBulkFamily] = useState<BulkFamily>("relay_control");
  const [bulkTemplateId, setBulkTemplateId] = useState("");
  const [bulkRelayOp, setBulkRelayOp] = useState<"disconnect" | "reconnect">("disconnect");
  const [bulkMeterText, setBulkMeterText] = useState("");
  const [bulkNotes, setBulkNotes] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);

  const [approvalOpen, setApprovalOpen] = useState<{
    commandId: string;
    mode: "approve" | "reject";
  } | null>(null);
  const [approvalNotes, setApprovalNotes] = useState("");
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);

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

  useEffect(() => {
    if (!bulkOpen || !currentUser) {
      return;
    }
    let cancelled = false;
    setTemplatesLoading(true);
    void (async () => {
      try {
        const res = await authorizedFetch<CommandTemplateListResponse>("/api/v1/command-templates");
        if (!cancelled) {
          setTemplates(res.items.filter((x) => x.is_active));
        }
      } catch {
        if (!cancelled) {
          setTemplates([]);
        }
      } finally {
        if (!cancelled) {
          setTemplatesLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authorizedFetch, bulkOpen, currentUser]);

  const bulkTemplateChoices = useMemo(
    () => templatesForBulkFamily(bulkFamily, templates),
    [bulkFamily, templates],
  );

  useEffect(() => {
    if (bulkTemplateChoices.length === 0) {
      setBulkTemplateId("");
      return;
    }
    if (!bulkTemplateChoices.some((t) => t.id === bulkTemplateId)) {
      setBulkTemplateId(bulkTemplateChoices[0]!.id);
    }
  }, [bulkTemplateChoices, bulkTemplateId]);

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

  const closeBulk = () => {
    setBulkOpen(false);
    setBulkError(null);
    setBulkMeterText("");
    setBulkNotes("");
  };

  const submitBulk = async () => {
    setBulkError(null);
    const meterIds = parseMeterIds(bulkMeterText);
    if (meterIds.length === 0) {
      setBulkError("Enter at least one valid meter UUID.");
      return;
    }
    if (!bulkTemplateId) {
      setBulkError("Select a command template.");
      return;
    }
    const body: Record<string, unknown> = {
      family: bulkFamily,
      meter_ids: meterIds,
      command_template_id: bulkTemplateId,
      notes: bulkNotes.trim() || null,
    };
    if (bulkFamily === "relay_control") {
      body.relay_operation = bulkRelayOp;
    } else {
      body.on_demand_read_operation = "read_billing_snapshot";
    }
    setBulkBusy(true);
    try {
      await authorizedFetch<BulkWizardResponse>("/api/v1/commands/bulk-requests", {
        method: "POST",
        body: JSON.stringify(body),
      });
      closeBulk();
      await load();
    } catch (e) {
      setBulkError(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setBulkBusy(false);
    }
  };

  const openApproval = (commandId: string, mode: "approve" | "reject") => {
    setApprovalNotes("");
    setApprovalError(null);
    setApprovalOpen({ commandId, mode });
  };

  const closeApproval = () => {
    setApprovalOpen(null);
    setApprovalError(null);
  };

  const submitApproval = async () => {
    if (!approvalOpen) {
      return;
    }
    setApprovalBusy(true);
    setApprovalError(null);
    const path =
      approvalOpen.mode === "approve"
        ? `/api/v1/commands/${approvalOpen.commandId}/approvals/approve`
        : `/api/v1/commands/${approvalOpen.commandId}/approvals/reject`;
    try {
      await authorizedFetch(path, {
        method: "POST",
        body: JSON.stringify({ approval_notes: approvalNotes.trim() || null }),
      });
      closeApproval();
      await load();
    } catch (e) {
      setApprovalError(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setApprovalBusy(false);
    }
  };

  if (isCheckingSession) {
    return <p className="ws-muted">Checking session…</p>;
  }

  if (!currentUser) {
    return <p className="ws-muted">Sign in to view commands.</p>;
  }

  return (
    <div className="ws-canvas ws-cmd-page">
      <header className="ws-cmd-header">
        <div className="ws-cmd-header-main">
          <div>
            <h1 className="ws-cmd-title">Commands</h1>
            <p className="ws-cmd-subtitle">Review activity, pending approvals, and submit bounded relay or read requests.</p>
          </div>
          <div className="ws-cmd-header-actions">
            <button type="button" className="ws-btn ws-btn-primary" onClick={() => setBulkOpen(true)}>
              Request commands
            </button>
          </div>
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
                      <th scope="col">Actions</th>
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
                      const canApprove = row.approval_status === "submitted_for_approval";
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
                          <td className="ws-cmd-actions-cell">
                            {canApprove ? (
                              <div className="ws-cmd-inline-actions">
                                <button
                                  type="button"
                                  className="ws-btn ws-btn-ghost ws-cmd-action-btn"
                                  onClick={() => openApproval(row.command_id, "approve")}
                                >
                                  Approve
                                </button>
                                <button
                                  type="button"
                                  className="ws-btn ws-btn-ghost ws-cmd-action-btn"
                                  onClick={() => openApproval(row.command_id, "reject")}
                                >
                                  Reject
                                </button>
                              </div>
                            ) : (
                              "—"
                            )}
                          </td>
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

      {bulkOpen ? (
        <div className="ws-cmd-dialog-backdrop" role="presentation" onClick={closeBulk}>
          <div
            className="ws-cmd-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="cmd-bulk-title"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.key === "Escape" && closeBulk()}
          >
            <h2 id="cmd-bulk-title" className="ws-cmd-dialog-title">
              Request commands
            </h2>
            <p className="ws-cmd-dialog-hint">
              Relay control and on-demand read only. Submissions enter the approvals queue when required.
            </p>
            <label className="ws-cmd-dialog-field">
              <span className="ws-cmd-dialog-label">Family</span>
              <select value={bulkFamily} onChange={(e) => setBulkFamily(e.target.value as BulkFamily)}>
                <option value="relay_control">Relay control</option>
                <option value="on_demand_read">On-demand read</option>
              </select>
            </label>
            {bulkFamily === "relay_control" ? (
              <label className="ws-cmd-dialog-field">
                <span className="ws-cmd-dialog-label">Relay operation</span>
                <select value={bulkRelayOp} onChange={(e) => setBulkRelayOp(e.target.value as "disconnect" | "reconnect")}>
                  <option value="disconnect">Disconnect</option>
                  <option value="reconnect">Reconnect</option>
                </select>
              </label>
            ) : null}
            <label className="ws-cmd-dialog-field">
              <span className="ws-cmd-dialog-label">Template</span>
              <select
                value={bulkTemplateId}
                onChange={(e) => setBulkTemplateId(e.target.value)}
                disabled={templatesLoading || bulkTemplateChoices.length === 0}
              >
                {bulkTemplateChoices.length === 0 ? (
                  <option value="">No matching templates</option>
                ) : (
                  bulkTemplateChoices.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.code} — {t.name}
                    </option>
                  ))
                )}
              </select>
            </label>
            <label className="ws-cmd-dialog-field">
              <span className="ws-cmd-dialog-label">Meter UUIDs</span>
              <textarea
                className="ws-cmd-dialog-textarea"
                value={bulkMeterText}
                onChange={(e) => setBulkMeterText(e.target.value)}
                rows={4}
                placeholder="One UUID per line or comma-separated"
                autoComplete="off"
              />
            </label>
            <label className="ws-cmd-dialog-field">
              <span className="ws-cmd-dialog-label">Notes</span>
              <input type="text" value={bulkNotes} onChange={(e) => setBulkNotes(e.target.value)} autoComplete="off" />
            </label>
            {bulkError ? (
              <p className="ws-alert" role="alert">
                {bulkError}
              </p>
            ) : null}
            <div className="ws-cmd-dialog-footer">
              <button type="button" className="ws-btn ws-btn-ghost" onClick={closeBulk} disabled={bulkBusy}>
                Cancel
              </button>
              <button type="button" className="ws-btn ws-btn-primary" onClick={() => void submitBulk()} disabled={bulkBusy}>
                {bulkBusy ? "Submitting…" : "Submit"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {approvalOpen ? (
        <div className="ws-cmd-dialog-backdrop" role="presentation" onClick={closeApproval}>
          <div
            className="ws-cmd-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="cmd-appr-title"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.key === "Escape" && closeApproval()}
          >
            <h2 id="cmd-appr-title" className="ws-cmd-dialog-title">
              {approvalOpen.mode === "approve" ? "Approve command" : "Reject command"}
            </h2>
            <p className="ws-cmd-dialog-hint ws-cmd-mono">{shortId(approvalOpen.commandId)}</p>
            <label className="ws-cmd-dialog-field">
              <span className="ws-cmd-dialog-label">Notes</span>
              <input type="text" value={approvalNotes} onChange={(e) => setApprovalNotes(e.target.value)} autoComplete="off" />
            </label>
            {approvalError ? (
              <p className="ws-alert" role="alert">
                {approvalError}
              </p>
            ) : null}
            <div className="ws-cmd-dialog-footer">
              <button type="button" className="ws-btn ws-btn-ghost" onClick={closeApproval} disabled={approvalBusy}>
                Cancel
              </button>
              <button
                type="button"
                className={approvalOpen.mode === "approve" ? "ws-btn ws-btn-primary" : "ws-btn ws-btn-ghost"}
                onClick={() => void submitApproval()}
                disabled={approvalBusy}
              >
                {approvalBusy ? "Working…" : approvalOpen.mode === "approve" ? "Approve" : "Reject"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
