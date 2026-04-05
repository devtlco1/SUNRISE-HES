"use client";

import type { ReactNode, SVGProps } from "react";

export type StatusTone = "positive" | "warning" | "danger" | "info" | "neutral";

type IconComponent = (props: SVGProps<SVGSVGElement>) => ReactNode;

export function cx(...classNames: Array<string | false | null | undefined>) {
  return classNames.filter(Boolean).join(" ");
}

export function formatDateTime(value: string | null): string {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

export function formatStatusLabel(value: string | null | undefined): string {
  if (!value) {
    return "Not recorded";
  }

  return value
    .split(/[_\s/.-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function getStatusTone(value: string | null | undefined): StatusTone {
  const normalized = value?.toLowerCase() ?? "";

  if (
    normalized.includes("online") ||
    normalized.includes("healthy") ||
    normalized.includes("success") ||
    normalized.includes("succeed") ||
    normalized.includes("completed") ||
    normalized.includes("active") ||
    normalized.includes("mapped") ||
    normalized.includes("available")
  ) {
    return "positive";
  }

  if (
    normalized.includes("offline") ||
    normalized.includes("failed") ||
    normalized.includes("timed") ||
    normalized.includes("critical") ||
    normalized.includes("error") ||
    normalized.includes("unlinked") ||
    normalized.includes("unknown")
  ) {
    return "danger";
  }

  if (
    normalized.includes("warning") ||
    normalized.includes("pending") ||
    normalized.includes("queued") ||
    normalized.includes("stale") ||
    normalized.includes("delayed") ||
    normalized.includes("intermittent") ||
    normalized.includes("service point only") ||
    normalized.includes("maintenance")
  ) {
    return "warning";
  }

  if (
    normalized.includes("info") ||
    normalized.includes("investigation") ||
    normalized.includes("acknowledged")
  ) {
    return "info";
  }

  return "neutral";
}

export function PageSectionHeader({
  eyebrow,
  title,
  description,
  aside,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  aside?: ReactNode;
}) {
  return (
    <div className="hes-page-section-header">
      <div>
        {eyebrow ? <p className="hes-page-section-eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {description ? <p className="hes-page-section-copy">{description}</p> : null}
      </div>
      {aside ? <div className="hes-page-section-aside">{aside}</div> : null}
    </div>
  );
}

export function SurfaceCard({
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
    <section className={cx("hes-surface-card", className)}>
      <div className="hes-surface-card-header">
        <div>
          <h3>{title}</h3>
          {description ? <p>{description}</p> : null}
        </div>
        {aside ? <div className="hes-surface-card-aside">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function StatCard({
  label,
  value,
  note,
  tone = "neutral",
  icon,
}: {
  label: string;
  value: string;
  note?: string;
  tone?: StatusTone;
  icon?: IconComponent;
}) {
  const Icon = icon;

  return (
    <article className={cx("hes-stat-card", `hes-stat-card-${tone}`)}>
      <div className="hes-stat-card-row">
        <div>
          <span className="hes-stat-card-label">{label}</span>
          <strong className="hes-stat-card-value">{value}</strong>
        </div>
        {Icon ? (
          <span className="hes-stat-card-icon">
            <Icon aria-hidden="true" />
          </span>
        ) : null}
      </div>
      {note ? <p className="hes-stat-card-note">{note}</p> : null}
    </article>
  );
}

export function StatusChip({
  label,
  tone,
}: {
  label: string;
  tone: StatusTone;
}) {
  return <span className={cx("hes-status-chip", `hes-status-chip-${tone}`)}>{label}</span>;
}

export function FilterToolbar({
  children,
  summary,
}: {
  children: ReactNode;
  summary?: ReactNode;
}) {
  return (
    <div className="hes-filter-toolbar">
      <div className="hes-filter-toolbar-controls">{children}</div>
      {summary ? <div className="hes-filter-toolbar-summary">{summary}</div> : null}
    </div>
  );
}

export function DataTableShell({
  title,
  description,
  aside,
  children,
  footer,
}: {
  title: string;
  description?: string;
  aside?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <section className="hes-table-shell">
      <div className="hes-surface-card-header">
        <div>
          <h3>{title}</h3>
          {description ? <p>{description}</p> : null}
        </div>
        {aside ? <div className="hes-surface-card-aside">{aside}</div> : null}
      </div>
      <div className="hes-table-scroll">{children}</div>
      {footer ? <div className="hes-table-footer">{footer}</div> : null}
    </section>
  );
}

export function SummaryList({
  items,
}: {
  items: Array<{
    label: string;
    value: string;
    tone?: StatusTone;
    note?: string;
  }>;
}) {
  return (
    <div className="hes-summary-list">
      {items.map((item) => (
        <div key={`${item.label}-${item.value}`} className="hes-summary-list-item">
          <div>
            <span>{item.label}</span>
            {item.note ? <small>{item.note}</small> : null}
          </div>
          <strong className={cx(item.tone ? `hes-tone-${item.tone}` : undefined)}>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

