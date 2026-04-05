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
  value: string;
  hint?: string;
};

function KpiCard({ label, value, hint }: KpiProps) {
  return (
    <div
      className="ws-kpi"
      tabIndex={0}
      title="Detailed views will open from rebuilt modules."
    >
      <div className="ws-kpi-label">{label}</div>
      <div className="ws-kpi-value">{value}</div>
      {hint ? <div className="ws-kpi-hint">{hint}</div> : null}
    </div>
  );
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
  return (
    <div className="ws-dash-page">
      <header className="ws-dash-header">
        <div>
          <h1 className="ws-page-title">Dashboard</h1>
          <p className="ws-page-subtitle">
            Situation overview and attention routing — lighter than module workspaces.
          </p>
        </div>
        {snapshot ? (
          <p className="ws-dash-asof" title="Snapshot time (browser-local display)">
            As of {fmtTime(snapshot.asOf)}
          </p>
        ) : null}
      </header>

      {loadError ? (
        <p className="ws-dash-banner" role="alert">
          {loadError}
        </p>
      ) : null}

      {snapshot && snapshot.errors.length > 0 ? (
        <ul className="ws-dash-banner ws-dash-banner--list" aria-label="Partial data errors">
          {snapshot.errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      ) : null}

      {loading ? <p className="ws-muted">Loading dashboard snapshot…</p> : null}

      {!loading && snapshot ? (
        <>
          <section className="ws-dash-section" aria-label="Key indicators">
            <div className="ws-kpi-grid">
              <KpiCard label="Total meters" value={fmt(snapshot.metersTotal)} />
              <KpiCard
                label="Online"
                value={fmt(snapshot.reachability?.online ?? null)}
                hint={
                  snapshot.reachability
                    ? `GIS sample ${snapshot.reachability.sampleSize} / ${fmt(snapshot.reachability.populationTotal)} · 24h last-seen`
                    : "GIS-linked sample unavailable"
                }
              />
              <KpiCard
                label="Offline"
                value={fmt(snapshot.reachability?.offline ?? null)}
                hint={
                  snapshot.reachability ? "Stale last-seen (>24h) within sample" : undefined
                }
              />
              <KpiCard
                label="Intermittent / unknown"
                value={fmt(snapshot.reachability?.unknown ?? null)}
                hint={
                  snapshot.reachability ? "No last-seen timestamp in sample" : undefined
                }
              />
              <KpiCard
                label="Commands (24h)"
                value={fmt(snapshot.commands24h)}
                hint={
                  snapshot.commandsRecentLimit != null
                    ? `From recent window (max ${snapshot.commandsRecentLimit})`
                    : undefined
                }
              />
              <KpiCard
                label="Pending / failed cmds"
                value={`${fmt(snapshot.commandsPendingLike)} / ${fmt(snapshot.commandsFailedLike)}`}
                hint="Recent command list only"
              />
              <KpiCard
                label="Critical alarms"
                value={fmt(snapshot.criticalOpenInWindow)}
                hint={
                  snapshot.eventsWindowLimit != null
                    ? `Open + critical in last ${snapshot.eventsWindowLimit} ingestions`
                    : undefined
                }
              />
              <KpiCard
                label="Active jobs"
                value={fmt(snapshot.activeJobRunsInWindow)}
                hint={
                  snapshot.jobRunsWindowLimit != null
                    ? `Pending / claimed / running in last ${snapshot.jobRunsWindowLimit} runs`
                    : undefined
                }
              />
            </div>
          </section>

          <section className="ws-dash-section" aria-label="Operational summaries">
            <div className="ws-dash-row ws-dash-row--3">
              <SummaryPanel title="Connectivity summary">
                <dl className="ws-dash-dl">
                  <dt>Communication endpoints</dt>
                  <dd>{fmt(snapshot.communicationEndpoints)}</dd>
                  <dt>GIS-linked meters (total)</dt>
                  <dd>{fmt(snapshot.reachability?.populationTotal ?? null)}</dd>
                  <dt>Reachability sample</dt>
                  <dd>
                    {snapshot.reachability
                      ? `${snapshot.reachability.sampleSize} meters in current slice`
                      : "—"}
                  </dd>
                </dl>
              </SummaryPanel>
              <SummaryPanel title="Command center summary">
                <dl className="ws-dash-dl">
                  <dt>Commands in last 24h</dt>
                  <dd>{fmt(snapshot.commands24h)}</dd>
                  <dt>Pending pipeline</dt>
                  <dd>{fmt(snapshot.commandsPendingLike)}</dd>
                  <dt>Failed / timed out</dt>
                  <dd>{fmt(snapshot.commandsFailedLike)}</dd>
                  <dt>Awaiting approval</dt>
                  <dd>{fmt(snapshot.approvalsPendingTotal)}</dd>
                </dl>
              </SummaryPanel>
              <SummaryPanel title="Alarm overview">
                <dl className="ws-dash-dl">
                  <dt>Critical · open (window)</dt>
                  <dd>{fmt(snapshot.criticalOpenInWindow)}</dd>
                  <dt>Warning · open (window)</dt>
                  <dd>{fmt(snapshot.warningOpenInWindow)}</dd>
                  <dt>Ingested events (total)</dt>
                  <dd>{fmt(snapshot.eventsIngestedTotal)}</dd>
                </dl>
              </SummaryPanel>
            </div>
          </section>

          <section className="ws-dash-section" aria-label="Secondary summaries">
            <div className="ws-dash-row ws-dash-row--2">
              <SummaryPanel title="Reading activity">
                {snapshot.readingActivityAvailable ? null : (
                  <p className="ws-dash-empty">
                    Fleet reading rollups are not exposed on a single endpoint yet. Billing,
                    interval, missing, and estimate breakdowns will appear here when the API
                    supports them.
                  </p>
                )}
              </SummaryPanel>
              <SummaryPanel title="GIS snapshot">
                <dl className="ws-dash-dl">
                  <dt>Mapped in sample</dt>
                  <dd>{fmt(snapshot.gisMappedInSample)}</dd>
                  <dt>Unlocated in sample</dt>
                  <dd>{fmt(snapshot.gisUnmappedInSample)}</dd>
                  <dt>Service points w/ stale meters</dt>
                  <dd>{fmt(snapshot.servicePointsWithOfflineInSample)}</dd>
                </dl>
                <p className="ws-kpi-hint ws-dash-gis-note">
                  Not a map workspace — counts are from the GIS-lite entity slice only.
                </p>
              </SummaryPanel>
            </div>
          </section>

          <section className="ws-dash-section" aria-labelledby="dash-attention">
            <h2 className="ws-dash-section-title" id="dash-attention">
              Priority / attention
            </h2>
            {snapshot.attention.length === 0 ? (
              <p className="ws-dash-empty">
                No priority items matched current indicators in the API windows above.
              </p>
            ) : (
              <ul className="ws-attention-list">
                {snapshot.attention.map((row) => (
                  <li key={row.id} className="ws-attention-item">
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
