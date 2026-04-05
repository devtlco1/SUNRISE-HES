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

  const fullNavigationSections = [
    {
      label: "Overview",
      items: [{ href: "/", label: "Dashboard home" }],
    },
    {
      label: "Operations",
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
      items: [
        { href: "/subscribers", label: "Subscribers" },
        { href: "/accounts", label: "Accounts" },
        { href: "/service-points", label: "Service Points" },
      ],
    },
    {
      label: "Infrastructure",
      items: [
        { href: "/gis-lite", label: "GIS Lite" },
        {
          href: "/transformers-substations",
          label: "Transformers / Substations",
        },
      ],
    },
  ];
  const dashboardHomeNavigationSections = [
    {
      label: "Foundation",
      items: [{ href: "/", label: "Dashboard home" }],
    },
    {
      label: "Primary launch areas",
      items: [
        { href: "/readings", label: "Readings review" },
        { href: "/connectivity", label: "Connectivity watch" },
        { href: "/jobs-events-alerts", label: "Alerts and activity" },
      ],
    },
    {
      label: "Supporting routes",
      items: [
        { href: "/meters", label: "Meter registry" },
        { href: "/commands", label: "Command center" },
        { href: "/gis-lite", label: "GIS Lite context" },
      ],
    },
  ];
  const navigationSections =
    navigationVariant === "dashboard-home"
      ? dashboardHomeNavigationSections
      : fullNavigationSections;
  const navigationRouteCount = fullNavigationSections.reduce(
    (total, section) => total + section.items.length,
    0,
  );

  return (
    <main
      className={`dashboard-shell${
        navigationVariant === "dashboard-home" ? " dashboard-shell-foundation" : ""
      }`}
    >
      <aside className="dashboard-sidebar">
        <div className="dashboard-sidebar-scroll">
          <div className="dashboard-brand">
            <Link className="dashboard-brand-link" href="/">
              Sunrise HES
            </Link>
            <p className="muted">
              {navigationVariant === "dashboard-home"
                ? "Phase 1 dashboard foundation for the new admin-style rollout."
                : "Safe gradual admin-shell adoption layered over the existing platform routes."}
            </p>
            <div className="dashboard-brand-badges">
              <span className="artifact-pill">
                {navigationVariant === "dashboard-home" ? "Phase 1 foundation" : "Stable routes"}
              </span>
              <span className="artifact-pill">
                {navigationRouteCount} shared surfaces
              </span>
            </div>
          </div>

          {navigationVariant === "dashboard-home" ? (
            <section className="dashboard-nav-callout">
              <p className="dashboard-nav-label">Current rollout</p>
              <strong>New dashboard home experience</strong>
              <p className="muted">
                Other routes remain available through launch cards, but this shell is
                intentionally centered on the rebuilt home experience first.
              </p>
            </section>
          ) : null}

          <div className="dashboard-nav-groups">
            {navigationSections.map((section) => (
              <section key={section.label} className="dashboard-nav-group">
                <p className="dashboard-nav-label">{section.label}</p>
                <div className="dashboard-nav-links">
                  {section.items.map((item) => (
                    <Link key={item.href} className="nav-link" href={item.href}>
                      {item.label}
                    </Link>
                  ))}
                </div>
              </section>
            ))}

            {currentMeterId ? (
              <section className="dashboard-nav-group">
                <p className="dashboard-nav-label">Context</p>
                <div className="dashboard-nav-links">
                  <Link className="nav-link" href={`/meters/${currentMeterId}`}>
                    Current meter
                  </Link>
                </div>
              </section>
            ) : null}
          </div>
        </div>
      </aside>

      <div className="dashboard-main">
        <div className="dashboard-main-frame">
          <header className="dashboard-topbar">
            <div className="dashboard-topbar-copy">
              <div>
                <p className="eyebrow">{eyebrow}</p>
                <h1>{title}</h1>
                <p className="lead">{description}</p>
              </div>
              <div className="dashboard-topbar-meta">
                <span className="artifact-pill">
                  {navigationVariant === "dashboard-home"
                    ? "Phase 1 new dashboard"
                    : "Safe shell adoption"}
                </span>
                <span className="artifact-pill">{eyebrow}</span>
              </div>
            </div>

            <div className="dashboard-topbar-actions">
              <div className="dashboard-search">
                <span className="muted">Platform routes remain unchanged</span>
              </div>
              <div className="dashboard-user-card">
                <strong>{currentUser?.full_name || currentUser?.username || "Guest"}</strong>
                <span className="muted">
                  {currentUser
                    ? currentUser.email
                    : isCheckingSession
                      ? "Session bootstrap in progress"
                      : `API ${apiBaseUrl}`}
                </span>
                {currentUser ? (
                  <button className="secondary-button" onClick={logout} type="button">
                    Sign out
                  </button>
                ) : null}
              </div>
            </div>
          </header>

          <section className="dashboard-content">
            {isCheckingSession ? (
              <section className="panel">
                <h2>Checking session</h2>
                <p className="muted">
                  Verifying the current operational session before loading the page.
                </p>
              </section>
            ) : null}

            {!isCheckingSession && !currentUser ? (
              <section className="panel auth-block-panel">
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
