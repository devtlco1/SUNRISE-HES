"use client";

import Link from "next/link";
import { type ReactNode } from "react";

import {
  SessionProvider,
  type AuthorizedFetch,
  type CurrentUser,
  useSession,
} from "./session-provider";
export type { AuthorizedFetch } from "./session-provider";

type OperationalShellRenderProps = {
  authorizedFetch: AuthorizedFetch;
  apiBaseUrl: string;
  currentUser: CurrentUser;
};

type OperationalShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  currentMeterId?: string;
  navigationVariant?: "default" | "dashboard-home";
  children: (props: OperationalShellRenderProps) => ReactNode;
};

type NavigationItem = {
  href: string;
  label: string;
  badge?: string;
};

type NavigationSection = {
  label: string;
  caption: string;
  items: NavigationItem[];
};

function getInitials(name: string | null | undefined): string {
  if (!name) {
    return "GU";
  }

  const parts = name
    .split(" ")
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 2);

  if (parts.length === 0) {
    return "GU";
  }

  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("");
}

export function OperationalShell({
  eyebrow,
  title,
  description,
  currentMeterId,
  navigationVariant = "default",
  children,
}: OperationalShellProps) {
  return (
    <SessionProvider>
      <OperationalShellInner
        eyebrow={eyebrow}
        title={title}
        description={description}
        currentMeterId={currentMeterId}
        navigationVariant={navigationVariant}
        children={children}
      />
    </SessionProvider>
  );
}

function OperationalShellInner({
  eyebrow,
  title,
  description,
  currentMeterId,
  navigationVariant = "default",
  children,
}: OperationalShellProps) {
  const {
    apiBaseUrl,
    authorizedFetch,
    currentUser,
    isCheckingSession,
    sessionError,
    logout,
  } = useSession();

  const migratedSection: NavigationSection = {
    label: "Migrated experience",
    caption: "Pages intentionally rebuilt in the new admin dashboard system.",
    items: [{ href: "/", label: "Dashboard home", badge: "Phase 1" }],
  };
  const fullNavigationSections: NavigationSection[] = [
    {
      label: "Operations",
      caption: "Control-center pages and operational drill-through surfaces.",
      items: [
        { href: "/meters", label: "Meters" },
        { href: "/readings", label: "Readings" },
        { href: "/commands", label: "Commands" },
        { href: "/connectivity", label: "Connectivity" },
        { href: "/jobs-events-alerts", label: "Jobs / Events / Alerts" },
        { href: "/audit-center", label: "Audit Center" },
      ],
    },
    {
      label: "Customers",
      caption: "Commercial and customer-context workspaces not yet visually migrated.",
      items: [
        { href: "/subscribers", label: "Subscribers" },
        { href: "/accounts", label: "Accounts" },
        { href: "/service-points", label: "Service Points" },
      ],
    },
    {
      label: "Infrastructure",
      caption: "GIS and network context workspaces still running on legacy page internals.",
      items: [
        { href: "/gis-lite", label: "GIS Lite" },
        {
          href: "/transformers-substations",
          label: "Transformers / Substations",
        },
      ],
    },
  ];
  const dashboardHomeNavigationSections: NavigationSection[] = [
    migratedSection,
    {
      label: "Primary workspaces",
      caption: "Most relevant operator destinations from the rebuilt home experience.",
      items: [
        { href: "/readings", label: "Readings review", badge: "Priority" },
        { href: "/connectivity", label: "Connectivity watch" },
        { href: "/jobs-events-alerts", label: "Alerts and activity" },
        { href: "/commands", label: "Command center" },
      ],
    },
    {
      label: "Legacy workspaces",
      caption: "Available routes that remain functional while awaiting full visual migration.",
      items: [
        { href: "/meters", label: "Meter registry" },
        { href: "/subscribers", label: "Subscribers" },
        { href: "/accounts", label: "Accounts" },
        { href: "/service-points", label: "Service points" },
        { href: "/gis-lite", label: "GIS Lite context" },
        { href: "/transformers-substations", label: "Transformers / substations" },
      ],
    },
  ];
  const navigationSections =
    navigationVariant === "dashboard-home"
      ? dashboardHomeNavigationSections
      : [migratedSection, ...fullNavigationSections];
  const navigationRouteCount = fullNavigationSections.reduce(
    (total, section) => total + section.items.length,
    0,
  );
  const isDashboardHome = navigationVariant === "dashboard-home";
  const currentUserName = currentUser?.full_name || currentUser?.username || "Guest user";
  const currentUserMeta = currentUser
    ? currentUser.email
    : isCheckingSession
      ? "Session bootstrap in progress"
      : `API ${apiBaseUrl}`;
  const pageStateLabel = isDashboardHome ? "Migrated dashboard" : "Legacy workspace";
  const pageStateNote = isDashboardHome
    ? "New shell, page rhythm, and card system are active on this route."
    : "Core functionality remains stable while the page-specific UI waits for migration.";

  return (
    <main className={`admin-shell${isDashboardHome ? " admin-shell-home" : ""}`}>
      <aside className="admin-sidebar">
        <div className="admin-sidebar-scroll">
          <div className="admin-sidebar-brand">
            <div className="admin-sidebar-brand-mark">SH</div>
            <div>
              <Link className="admin-sidebar-brand-link" href="/">
                Sunrise HES
              </Link>
              <p className="muted">
                {isDashboardHome
                  ? "New admin dashboard foundation anchored on the rebuilt home experience."
                  : "Shared shell foundation with clear separation between migrated and legacy routes."}
              </p>
            </div>
          </div>

          <section className="admin-sidebar-spotlight">
            <p className="admin-sidebar-kicker">
              {isDashboardHome ? "Current rollout" : "Migration status"}
            </p>
            <strong>{isDashboardHome ? "Dashboard home is the active migrated page." : "This route is still using legacy page internals."}</strong>
            <p className="muted">{pageStateNote}</p>
            <div className="admin-sidebar-badges">
              <span className="artifact-pill">{pageStateLabel}</span>
              <span className="artifact-pill">{navigationRouteCount} platform routes</span>
            </div>
          </section>

          <div className="admin-sidebar-nav">
            {navigationSections.map((section) => (
              <section key={section.label} className="admin-nav-section">
                <div className="admin-nav-section-heading">
                  <p className="admin-sidebar-kicker">{section.label}</p>
                  <p className="muted">{section.caption}</p>
                </div>
                <div className="admin-nav-link-list">
                  {section.items.map((item) => (
                    <Link key={item.href} className="admin-nav-link" href={item.href}>
                      <span>{item.label}</span>
                      {item.badge ? (
                        <span aria-hidden="true" className="admin-nav-link-badge">
                          {item.badge}
                        </span>
                      ) : null}
                    </Link>
                  ))}
                </div>
              </section>
            ))}

            {currentMeterId ? (
              <section className="admin-nav-section">
                <div className="admin-nav-section-heading">
                  <p className="admin-sidebar-kicker">Context</p>
                  <p className="muted">Current entity drill-through preserved inside the shared shell.</p>
                </div>
                <div className="admin-nav-link-list">
                  <Link className="admin-nav-link" href={`/meters/${currentMeterId}`}>
                    <span>Current meter</span>
                    <span aria-hidden="true" className="admin-nav-link-badge">
                      Context
                    </span>
                  </Link>
                </div>
              </section>
            ) : null}
          </div>
        </div>
      </aside>

      <div className="admin-main">
        <div className="admin-main-frame">
          <header className="admin-header">
            <div className="admin-header-copy">
              <div className="admin-header-breadcrumbs">
                <span className="admin-header-breadcrumb">Sunrise HES</span>
                <span className="admin-header-breadcrumb">/</span>
                <span className="admin-header-breadcrumb">{eyebrow}</span>
              </div>
              <div className="admin-header-title-row">
                <div>
                  <p className="eyebrow">{eyebrow}</p>
                  <h1>{title}</h1>
                  <p className="lead">{description}</p>
                </div>
                <div className="admin-header-title-meta">
                  <span className="artifact-pill">{pageStateLabel}</span>
                  <span className="artifact-pill">
                    {isDashboardHome ? "Next step foundation" : "Route preserved"}
                  </span>
                </div>
              </div>
            </div>

            <div className="admin-header-actions">
              <div className="admin-header-command">
                <span className="admin-header-command-label">Migration guardrail</span>
                <strong>Routes, auth/session flow, and backend contracts remain unchanged.</strong>
              </div>
              <div className="admin-header-user-card">
                <div className="admin-header-user-avatar">{getInitials(currentUserName)}</div>
                <div className="admin-header-user-meta">
                  <strong>{currentUserName}</strong>
                  <span className="muted">{currentUserMeta}</span>
                </div>
                {currentUser ? (
                  <button className="secondary-button" onClick={logout} type="button">
                    Sign out
                  </button>
                ) : null}
              </div>
            </div>
          </header>

          <section className="admin-content">
            {isCheckingSession ? (
              <section className="panel admin-state-panel">
                <h2>Checking session</h2>
                <p className="muted">
                  Verifying the current operational session before loading the page.
                </p>
              </section>
            ) : null}

            {!isCheckingSession && !currentUser ? (
              <section className="panel auth-block-panel admin-state-panel">
                <div className="section-heading">
                  <div>
                    <h2>Session required</h2>
                    <p className="muted">
                      Sign in through the bounded auth entry flow before opening the
                      operational pages.
                    </p>
                  </div>
                </div>

                <div className="artifact-row">
                  <Link className="primary-button" href="/login">
                    Open login
                  </Link>
                  <Link className="secondary-button" href="/forgot-password">
                    Forgot password
                  </Link>
                </div>

                {sessionError ? <p className="error-banner">{sessionError}</p> : null}
              </section>
            ) : null}

            {!isCheckingSession && currentUser ? (
              <>{children({ authorizedFetch, apiBaseUrl, currentUser })}</>
            ) : null}
          </section>
        </div>
      </div>
    </main>
  );
}
