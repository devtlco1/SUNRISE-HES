"use client";

import { type JSX, type ReactNode, type SVGProps } from "react";

type DashboardIcon = (props: SVGProps<SVGSVGElement>) => JSX.Element;

function cx(...classNames: Array<string | false | null | undefined>) {
  return classNames.filter(Boolean).join(" ");
}

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
    <section className={cx("na-surface-card", className)}>
      <div className="na-surface-card-header">
        <div>
          <h3>{title}</h3>
          {description ? <p className="na-card-copy">{description}</p> : null}
        </div>
        {aside ? <div className="na-surface-card-aside">{aside}</div> : null}
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
    <section className={cx("na-section-card", className)}>
      <div className="na-section-card-header">
        <div>
          {eyebrow ? <p className="na-section-eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
          <p className="na-card-copy">{description}</p>
        </div>
        {aside ? <div className="na-surface-card-aside">{aside}</div> : null}
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
  icon,
  meta,
}: {
  label: string;
  value: string;
  note: string;
  accent?: "default" | "positive" | "warning" | "danger";
  icon?: DashboardIcon;
  meta?: string;
}) {
  const Icon = icon;

  return (
    <article className={cx("na-overview-card", `na-overview-card-${accent}`)}>
      {Icon ? (
        <div className="na-overview-card-icon">
          <Icon aria-hidden="true" />
        </div>
      ) : null}

      <div className="na-overview-card-content">
        <div className="na-overview-card-row">
          <dl>
            <dt className="na-overview-card-value">{value}</dt>
            <dd className="na-overview-card-label">{label}</dd>
          </dl>
          {meta ? <span className={cx("na-status-pill", `na-status-pill-${accent}`)}>{meta}</span> : null}
        </div>
        <p className="na-card-copy">{note}</p>
      </div>
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
    <article className="na-launch-card">
      <div className="na-launch-card-header">
        <span className="na-launch-card-label">{label}</span>
        <strong>{title}</strong>
        <p className="na-card-copy">{summary}</p>
      </div>

      <div className="na-launch-card-highlights">
        {highlights.map((highlight) => (
          <div key={highlight} className="na-launch-card-highlight">
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
    <section className="na-table-card">
      <div className="na-surface-card-header">
        <div>
          <h3>{title}</h3>
          {description ? <p className="na-card-copy">{description}</p> : null}
        </div>
        {aside ? <div className="na-surface-card-aside">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}
