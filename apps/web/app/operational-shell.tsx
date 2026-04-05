"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, type SVGProps, useEffect, useMemo, useState } from "react";

import {
  SessionProvider,
  type AuthorizedFetch,
  type CurrentUser,
  useSession,
} from "./session-provider";
export type { AuthorizedFetch } from "./session-provider";
import {
  FourCircleIcon,
  HomeIcon,
  MenuIcon,
  PieChartIcon,
  SearchIcon,
  TableIcon,
  UserIcon,
} from "./nextadmin-icons";

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

type NavigationItem = {
  href: string;
  label: string;
  icon: (props: SVGProps<SVGSVGElement>) => ReactNode;
  badge?: string;
};

type NavigationSection = {
  label: string;
  items: NavigationItem[];
  muted?: boolean;
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
  const pathname = usePathname() ?? "/";
  const {
    apiBaseUrl,
    authorizedFetch,
    currentUser,
    isCheckingSession,
    sessionError,
    logout,
  } = useSession();
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return undefined;
    }

    const mediaQuery = window.matchMedia("(max-width: 1024px)");
    const syncViewport = (matches: boolean) => {
      setIsMobileViewport(matches);
      setIsMobileSidebarOpen(!matches);
    };

    syncViewport(mediaQuery.matches);

    const listener = (event: MediaQueryListEvent) => {
      syncViewport(event.matches);
    };

    mediaQuery.addEventListener("change", listener);
    return () => mediaQuery.removeEventListener("change", listener);
  }, []);

  const navigationSections: NavigationSection[] = [
    {
      label: "PRIMARY",
      items: [
        { href: "/", label: "Dashboard", icon: HomeIcon, badge: "Live" },
        { href: "/meters", label: "Meters", icon: TableIcon },
      ],
    },
    {
      label: "OPERATIONS",
      items: [
        { href: "/connectivity", label: "Connectivity", icon: PieChartIcon },
        { href: "/commands", label: "Commands", icon: FourCircleIcon },
        { href: "/readings", label: "Readings", icon: PieChartIcon },
      ],
    },
    {
      label: "ADDITIONAL MODULES",
      muted: true,
      items: [
        { href: "/jobs-events-alerts", label: "Jobs / Events / Alerts", icon: FourCircleIcon },
        { href: "/subscribers", label: "Subscribers", icon: UserIcon },
        { href: "/accounts", label: "Accounts", icon: TableIcon },
        { href: "/service-points", label: "Service Points", icon: FourCircleIcon },
        { href: "/gis-lite", label: "GIS Lite", icon: PieChartIcon },
        {
          href: "/transformers-substations",
          label: "Transformers / Substations",
          icon: FourCircleIcon,
        },
        { href: "/audit-center", label: "Audit Center", icon: TableIcon },
      ],
    },
  ];

  const currentUserName = currentUser?.full_name || currentUser?.username || "Guest user";
  const currentUserMeta = currentUser
    ? currentUser.email
    : isCheckingSession
      ? "Session bootstrap in progress"
      : `API ${apiBaseUrl}`;
  const shellPills = useMemo(
    () => [
      currentUser ? "Authenticated" : "Session required",
      "English workspace",
      "LTR",
    ],
    [currentUser],
  );

  function closeMobileSidebar() {
    if (isMobileViewport) {
      setIsMobileSidebarOpen(false);
    }
  }

  function toggleSidebar() {
    if (isMobileViewport) {
      setIsMobileSidebarOpen((currentValue) => !currentValue);
    }
  }

  function isItemActive(href: string) {
    if (href === "/") {
      return pathname === "/";
    }

    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <main className="na-layout">
      {isMobileViewport && isMobileSidebarOpen ? (
        <button
          aria-label="Close navigation"
          className="na-sidebar-overlay"
          onClick={closeMobileSidebar}
          type="button"
        />
      ) : null}

      <aside
        className={`na-sidebar${isMobileSidebarOpen ? " is-open" : ""}${isMobileViewport ? " is-mobile" : ""}`}
      >
        <div className="na-sidebar-inner">
          <div className="na-sidebar-brand-row">
            <Link className="na-sidebar-brand" href="/" onClick={closeMobileSidebar}>
              <div className="na-sidebar-brand-mark">SH</div>
              <div>
                <strong>Sunrise HES</strong>
                <span>AMI operations platform</span>
              </div>
            </Link>
          </div>

          <section className="na-sidebar-callout hes-sidebar-callout">
            <span className="na-sidebar-callout-eyebrow">Active context</span>
            <strong>{title}</strong>
            <p>{description}</p>
            <div className="na-sidebar-callout-pills">
              <span className="na-status-pill na-status-pill-positive">
                {currentUser ? "Authenticated" : "Session required"}
              </span>
            </div>
          </section>

          <div className="na-sidebar-nav">
            {navigationSections.map((section) => (
              <section
                key={section.label}
                className={`na-sidebar-section${section.muted ? " hes-sidebar-section-muted" : ""}`}
              >
                <h2>{section.label}</h2>
                <ul>
                  {section.items.map((item) => {
                    const isActive = isItemActive(item.href);
                    const Icon = item.icon;

                    return (
                      <li key={item.href}>
                        <Link
                          aria-current={isActive ? "page" : undefined}
                          className={`na-menu-link${isActive ? " is-active" : ""}`}
                          href={item.href}
                          onClick={closeMobileSidebar}
                        >
                          <Icon aria-hidden="true" className="na-menu-link-icon" />
                          <span>{item.label}</span>
                          {item.badge ? (
                            <span aria-hidden="true" className="na-menu-link-badge">
                              {item.badge}
                            </span>
                          ) : null}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}

            {currentMeterId ? (
              <section className="na-sidebar-section hes-sidebar-section-muted">
                <h2>CONTEXT</h2>
                <ul>
                  <li>
                    <Link
                      className={`na-menu-link${isItemActive(`/meters/${currentMeterId}`) ? " is-active" : ""}`}
                      href={`/meters/${currentMeterId}`}
                      onClick={closeMobileSidebar}
                    >
                      <TableIcon aria-hidden="true" className="na-menu-link-icon" />
                      <span>Current meter</span>
                      <span aria-hidden="true" className="na-menu-link-badge">
                        Detail
                      </span>
                    </Link>
                  </li>
                </ul>
              </section>
            ) : null}
          </div>
        </div>
      </aside>

      <div className="na-page">
        <header className="na-topbar hes-topbar">
          <div className="na-topbar-left">
            <div className="na-topbar-mobile-row">
              <button className="na-menu-toggle" onClick={toggleSidebar} type="button">
                <MenuIcon aria-hidden="true" />
                <span className="sr-only">Toggle sidebar</span>
              </button>
              <div className="na-topbar-breadcrumbs">
                <span>Sunrise HES</span>
                <span>/</span>
                <span>{eyebrow}</span>
              </div>
            </div>

            <div className="na-topbar-copy">
              <p className="eyebrow">{eyebrow}</p>
              <h1>{title}</h1>
              <p className="lead">{description}</p>
            </div>
          </div>

          <div className="na-topbar-right">
            <label className="na-search" aria-label="Search">
              <SearchIcon aria-hidden="true" />
              <input placeholder="Search meter, account, command, or event" readOnly type="search" />
            </label>

            <div className="na-topbar-pills">
              {shellPills.map((pill) => (
                <span key={pill} className="na-status-pill">
                  {pill}
                </span>
              ))}
            </div>

            <div className="na-user-card">
              <div className="na-user-avatar">{getInitials(currentUserName)}</div>
              <div className="na-user-copy">
                <strong>{currentUserName}</strong>
                <span>{currentUserMeta}</span>
              </div>
              {currentUser ? (
                <button className="secondary-button na-signout-button" onClick={logout} type="button">
                  Sign out
                </button>
              ) : null}
            </div>
          </div>
        </header>

        <section className="na-content">
          {isCheckingSession ? (
            <section className="panel na-auth-state-card">
              <h2>Checking session</h2>
              <p className="muted">
                Verifying the current operational session before loading the page.
              </p>
            </section>
          ) : null}

          {!isCheckingSession && !currentUser ? (
            <section className="panel auth-block-panel na-auth-state-card">
              <div className="section-heading">
                <div>
                  <h2>Session required</h2>
                  <p className="muted">
                    Sign in through the existing auth flow before opening the operational
                    workspace.
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
