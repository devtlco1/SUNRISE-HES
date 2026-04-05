import type { ReactNode } from "react";

import type { DashboardSnapshot } from "./fetch-dashboard-data";

function fmt(n: number | null): string {
  if (n === null || Number.isNaN(n)) {
    return "—";
  }
  return n.toLocaleString("en-US");
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-US", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

type KpiProps = {
  label: string;
  value: ReactNode;
  accent?: "neutral" | "success" | "danger" | "warning" | "info" | "muted";
};

function KpiCard({ label, value, accent = "neutral" }: KpiProps) {
  return (
    <div
      className={`ws-kpi ws-kpi--accent-${accent}`}
      tabIndex={0}
      aria-label={label}
    >
      <div className="ws-kpi-label">{label}</div>
      <div className="ws-kpi-value">{value}</div>
    </div>
  );
}

function metricTone(
  value: number | null,
  goodWhen: "zero" | "nonzero",
): "success" | "danger" | "warning" | "muted" | "neutral" {
  if (value === null) {
    return "muted";
  }
  if (goodWhen === "zero") {
    return value === 0 ? "success" : "danger";
  }
  return value > 0 ? "success" : "muted";
}

function Metric({ children, tone }: { children: ReactNode; tone: KpiProps["accent"] }) {
  return <span className={`ws-metric ws-metric--${tone}`}>{children}</span>;
}

type PanelProps = {
  title: string;
  children: ReactNode;
};

function SummaryPanel({ title, children }: PanelProps) {
  return (
    <section className="ws-dash-panel" aria-labelledby={slugId(title)}>
      <h2 className="ws-dash-panel-title" id={slugId(title)}>
        {title}
      </h2>
      <div className="ws-dash-panel-body">{children}</div>
    </section>
  );
}

function slugId(title: string): string {
  return `dash-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;
}

export type DashboardHomeViewProps = {
  snapshot: DashboardSnapshot | null;
  loading: boolean;
  loadError: string | null;
};

export function DashboardHomeView({ snapshot, loading, loadError }: DashboardHomeViewProps) {
  const crit = snapshot?.criticalOpenInWindow ?? null;
  const warnOpen = snapshot?.warningOpenInWindow ?? null;
  const offline = snapshot?.reachability?.offline ?? null;
  const unknown = snapshot?.reachability?.unknown ?? null;
  const failedCmds = snapshot?.commandsFailedLike ?? null;
  const staleSp = snapshot?.servicePointsWithOfflineInSample ?? null;

  return (
    <div className="ws-dash-page">
      <header className="ws-dash-header">
        <div>
          <h1 className="ws-page-title">Dashboard</h1>
          <p className="ws-page-subtitle">Fleet status, commands, alarms, and priority items.</p>
        </div>
        {snapshot ? <p className="ws-dash-asof">As of {fmtTime(snapshot.asOf)}</p> : null}
      </header>

      {loadError ? (
        <p className="ws-dash-banner" role="alert">
          {loadError}
        </p>
      ) : null}

      {snapshot && snapshot.errors.length > 0 ? (
        <ul className="ws-dash-banner ws-dash-banner--list" aria-label="Refresh notes">
          {snapshot.errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      ) : null}

      {loading ? <p className="ws-dash-loading">Loading…</p> : null}

      {!loading && snapshot ? (
        <>
          <section className="ws-dash-section" aria-label="Key indicators">
            <div className="ws-kpi-grid">
              <KpiCard label="Total meters" value={fmt(snapshot.metersTotal)} accent="neutral" />
              <KpiCard
                label="Online"
                value={fmt(snapshot.reachability?.online ?? null)}
                accent={
                  snapshot.reachability == null
                    ? "muted"
                    : snapshot.reachability.online > 0
                      ? "success"
                      : "warning"
                }
              />
              <KpiCard
                label="Offline"
                value={fmt(snapshot.reachability?.offline ?? null)}
                accent={
                  offline === null ? "muted" : offline > 0 ? "danger" : "success"
                }
              />
              <KpiCard
                label="Intermittent / unknown"
                value={fmt(snapshot.reachability?.unknown ?? null)}
                accent={
                  unknown === null ? "muted" : unknown > 0 ? "warning" : "success"
                }
              />
              <KpiCard
                label="Commands (24h)"
                value={fmt(snapshot.commands24h)}
                accent={snapshot.commands24h == null ? "muted" : "info"}
              />
              <KpiCard
                label="Pending / failed cmds"
                value={
                  snapshot.commandsPendingLike != null && snapshot.commandsFailedLike != null ? (
                    <>
                      <span className="ws-metric ws-metric--warning">
                        {fmt(snapshot.commandsPendingLike)}
                      </span>
                      <span className="ws-kpi-value-sep"> / </span>
                      <span className="ws-metric ws-metric--danger">
                        {fmt(snapshot.commandsFailedLike)}
                      </span>
                    </>
                  ) : (
                    "—"
                  )
                }
                accent="neutral"
              />
              <KpiCard
                label="Critical alarms"
                value={fmt(snapshot.criticalOpenInWindow)}
                accent={metricTone(crit, "zero")}
              />
              <KpiCard
                label="Active jobs"
                value={fmt(snapshot.activeJobRunsInWindow)}
                accent={
                  snapshot.activeJobRunsInWindow == null
                    ? "muted"
                    : snapshot.activeJobRunsInWindow > 0
                      ? "info"
                      : "muted"
                }
              />
            </div>
          </section>

          <section className="ws-dash-section" aria-label="Operational summaries">
            <div className="ws-dash-row ws-dash-row--3">
              <SummaryPanel title="Connectivity summary">
                <dl className="ws-dash-dl">
                  <dt>Communication endpoints</dt>
                  <dd>
                    <Metric tone="neutral">{fmt(snapshot.communicationEndpoints)}</Metric>
                  </dd>
                  <dt>GIS-linked meters</dt>
                  <dd>
                    <Metric tone="neutral">{fmt(snapshot.reachability?.populationTotal ?? null)}</Metric>
                  </dd>
                  <dt>Coverage sample</dt>
                  <dd>
                    <Metric tone="muted">
                      {snapshot.reachability
                        ? `${snapshot.reachability.sampleSize} / ${fmt(snapshot.reachability.populationTotal)}`
                        : "—"}
                    </Metric>
                  </dd>
                </dl>
              </SummaryPanel>
              <SummaryPanel title="Command center summary">
                <dl className="ws-dash-dl">
                  <dt>Commands (24h)</dt>
                  <dd>
                    <Metric tone={snapshot.commands24h == null ? "muted" : "info"}>
                      {fmt(snapshot.commands24h)}
                    </Metric>
                  </dd>
                  <dt>Pending</dt>
                  <dd>
                    <Metric
                      tone={
                        snapshot.commandsPendingLike == null
                          ? "muted"
                          : snapshot.commandsPendingLike > 0
                            ? "warning"
                            : "muted"
                      }
                    >
                      {fmt(snapshot.commandsPendingLike)}
                    </Metric>
                  </dd>
                  <dt>Failed / timed out</dt>
                  <dd>
                    <Metric
                      tone={
                        failedCmds == null
                          ? "muted"
                          : failedCmds > 0
                            ? "danger"
                            : "success"
                      }
                    >
                      {fmt(snapshot.commandsFailedLike)}
                    </Metric>
                  </dd>
                  <dt>Awaiting approval</dt>
                  <dd>
                    <Metric
                      tone={
                        snapshot.approvalsPendingTotal == null
                          ? "muted"
                          : snapshot.approvalsPendingTotal > 0
                            ? "warning"
                            : "muted"
                      }
                    >
                      {fmt(snapshot.approvalsPendingTotal)}
                    </Metric>
                  </dd>
                </dl>
              </SummaryPanel>
              <SummaryPanel title="Alarm overview">
                <dl className="ws-dash-dl">
                  <dt>Critical · open</dt>
                  <dd>
                    <Metric tone={metricTone(crit, "zero")}>{fmt(snapshot.criticalOpenInWindow)}</Metric>
                  </dd>
                  <dt>Warning · open</dt>
                  <dd>
                    <Metric
                      tone={
                        warnOpen === null ? "muted" : warnOpen > 0 ? "warning" : "success"
                      }
                    >
                      {fmt(snapshot.warningOpenInWindow)}
                    </Metric>
                  </dd>
                  <dt>Events recorded</dt>
                  <dd>
                    <Metric tone={snapshot.eventsIngestedTotal == null ? "muted" : "info"}>
                      {fmt(snapshot.eventsIngestedTotal)}
                    </Metric>
                  </dd>
                </dl>
              </SummaryPanel>
            </div>
          </section>

          <section className="ws-dash-section" aria-label="Secondary summaries">
            <div className="ws-dash-row ws-dash-row--2">
              <SummaryPanel title="Reading activity">
                {snapshot.readingActivityAvailable ? null : (
                  <p className="ws-dash-empty">Data not available yet.</p>
                )}
              </SummaryPanel>
              <SummaryPanel title="GIS snapshot">
                <dl className="ws-dash-dl">
                  <dt>Mapped</dt>
                  <dd>
                    <Metric tone={snapshot.gisMappedInSample == null ? "muted" : "success"}>
                      {fmt(snapshot.gisMappedInSample)}
                    </Metric>
                  </dd>
                  <dt>Unlocated</dt>
                  <dd>
                    <Metric tone="muted">{fmt(snapshot.gisUnmappedInSample)}</Metric>
                  </dd>
                  <dt>Service points · stale</dt>
                  <dd>
                    <Metric
                      tone={
                        staleSp == null
                          ? "muted"
                          : staleSp > 0
                            ? "warning"
                            : "success"
                      }
                    >
                      {fmt(snapshot.servicePointsWithOfflineInSample)}
                    </Metric>
                  </dd>
                </dl>
              </SummaryPanel>
            </div>
          </section>

          <section
            className="ws-dash-section ws-dash-section--attention"
            aria-labelledby="dash-attention"
          >
            <h2 className="ws-dash-section-title ws-dash-section-title--attention" id="dash-attention">
              Priority / attention
            </h2>
            {snapshot.attention.length === 0 ? (
              <p className="ws-dash-empty ws-dash-empty--ok">No active issues.</p>
            ) : (
              <ul className="ws-attention-list">
                {snapshot.attention.map((row) => (
                  <li
                    key={row.id}
                    className={`ws-attention-item ws-attention-item--${row.kind}`}
                  >
                    <span className="ws-attention-dot" aria-hidden />
                    <div className="ws-attention-main">
                      <span className="ws-attention-label">{row.label}</span>
                      <span className="ws-attention-detail">{row.detail}</span>
                    </div>
                    <time className="ws-attention-time" dateTime={row.at}>
                      {fmtTime(row.at)}
                    </time>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
