"use client";

import { type ReactNode } from "react";

export function DashboardPanel({
  title,
  description,
  aside,
  children,
  className,
}: {
  title: string;
  description?: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`dashboard-panel${className ? ` ${className}` : ""}`}>
      <div className="dashboard-panel-header">
        <div>
          <h3>{title}</h3>
          {description ? <p className="muted">{description}</p> : null}
        </div>
        {aside ? <div className="dashboard-panel-aside">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function DashboardSection({
  eyebrow,
  title,
  description,
  aside,
  children,
  className,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`dashboard-foundation-section${className ? ` ${className}` : ""}`}>
      <div className="dashboard-foundation-section-header">
        <div>
          {eyebrow ? <p className="dashboard-foundation-section-eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
          <p className="muted">{description}</p>
        </div>
        {aside ? <div className="dashboard-foundation-section-aside">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function DashboardMetricCard({
  label,
  value,
  note,
  accent = "default",
}: {
  label: string;
  value: string;
  note: string;
  accent?: "default" | "positive" | "warning" | "danger";
}) {
  return (
    <article className={`dashboard-metric-card dashboard-metric-card-${accent}`}>
      <span className="dashboard-metric-label">{label}</span>
      <strong>{value}</strong>
      <p className="muted">{note}</p>
    </article>
  );
}

export function DashboardLaunchCard({
  label,
  title,
  summary,
  highlights,
  actions,
}: {
  label: string;
  title: string;
  summary: string;
  highlights: string[];
  actions: ReactNode;
}) {
  return (
    <article className="dashboard-launch-card">
      <div className="dashboard-launch-card-header">
        <span className="dashboard-metric-label">{label}</span>
        <strong>{title}</strong>
        <p className="muted">{summary}</p>
      </div>
      <div className="dashboard-launch-highlights">
        {highlights.map((highlight) => (
          <div key={highlight} className="dashboard-launch-highlight">
            {highlight}
          </div>
        ))}
      </div>
      <div className="artifact-row">{actions}</div>
    </article>
  );
}

export function DashboardTableShell({
  title,
  description,
  aside,
  children,
}: {
  title: string;
  description?: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="dashboard-table-shell">
      <div className="dashboard-panel-header">
        <div>
          <h3>{title}</h3>
          {description ? <p className="muted">{description}</p> : null}
        </div>
        {aside ? <div className="dashboard-panel-aside">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}
