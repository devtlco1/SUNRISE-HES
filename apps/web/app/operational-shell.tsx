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
  children: (props: OperationalShellRenderProps) => ReactNode;
};

export function OperationalShell({
  eyebrow,
  title,
  description,
  currentMeterId,
  children,
}: OperationalShellProps) {
  return (
    <SessionProvider>
      <OperationalShellInner
        eyebrow={eyebrow}
        title={title}
        description={description}
        currentMeterId={currentMeterId}
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

  const navigationSections = [
    {
      label: "Overview",
      items: [{ href: "/", label: "Dashboard home" }],
    },
    {
      label: "Operations",
      items: [
        { href: "/meters", label: "Meters" },
        { href: "/commands", label: "Commands" },
        { href: "/connectivity", label: "Connectivity" },
        { href: "/jobs-events-alerts", label: "Jobs / Events / Alerts" },
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

  return (
    <main className="dashboard-shell">
      <aside className="dashboard-sidebar">
        <div className="dashboard-brand">
          <Link className="dashboard-brand-link" href="/">
            Sunrise HES
          </Link>
          <p className="muted">
            NextAdmin-inspired operational shell layered over the existing platform
            routes.
          </p>
        </div>

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
      </aside>

      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <div>
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            <p className="lead">{description}</p>
          </div>

          <div className="dashboard-topbar-actions">
            <div className="dashboard-search">
              <span className="muted">Platform routes remain unchanged</span>
            </div>
            <div className="dashboard-user-card">
              <strong>{currentUser?.full_name || currentUser?.username || "Guest"}</strong>
              <span className="muted">
                {currentUser ? currentUser.email : `API ${apiBaseUrl}`}
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
    </main>
  );
}
