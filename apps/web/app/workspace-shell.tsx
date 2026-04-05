"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { SessionProvider, useSession } from "./session-provider";

export type { AuthorizedFetch } from "./session-provider";

type WorkspaceShellProps = {
  children: ReactNode;
};

function WorkspaceChrome({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const { currentUser, isCheckingSession, sessionError, logout } = useSession();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  const dashboardActive = pathname === "/";

  return (
    <div className="ws-root">
      {mobileNavOpen ? (
        <button
          type="button"
          className="ws-backdrop"
          aria-label="Close menu"
          onClick={() => setMobileNavOpen(false)}
        />
      ) : null}

      <aside className={`ws-sidebar${mobileNavOpen ? " is-open" : ""}`}>
        <div className="ws-sidebar-brand">
          <span className="ws-sidebar-mark">SH</span>
          <div>
            <div className="ws-sidebar-title">Sunrise HES</div>
            <div className="ws-sidebar-tag">Operations</div>
          </div>
        </div>
        <nav id="ws-sidebar-nav" className="ws-nav" aria-label="Primary">
          <Link
            href="/"
            className={`ws-nav-item${dashboardActive ? " is-active" : ""}`}
            aria-current={dashboardActive ? "page" : undefined}
          >
            Dashboard
          </Link>
        </nav>
      </aside>

      <div className="ws-column">
        <header className="ws-header">
          <div className="ws-header-left">
            <button
              type="button"
              className="ws-menu-btn"
              aria-expanded={mobileNavOpen}
              aria-controls="ws-sidebar-nav"
              onClick={() => setMobileNavOpen((o) => !o)}
            >
              Menu
            </button>
            <span className="ws-header-context">Sunrise HES</span>
          </div>
          <div className="ws-header-right">
            {isCheckingSession ? (
              <span className="ws-muted">Session…</span>
            ) : currentUser ? (
              <>
                <span className="ws-user-label">{currentUser.email}</span>
                <button type="button" className="ws-btn ws-btn-ghost" onClick={logout}>
                  Sign out
                </button>
              </>
            ) : (
              <Link href="/login" className="ws-btn ws-btn-primary">
                Sign in
              </Link>
            )}
          </div>
        </header>

        <main className="ws-main">
          {sessionError ? (
            <p className="ws-alert" role="alert">
              {sessionError}
            </p>
          ) : null}
          {children}
        </main>

        <footer className="ws-footer" role="contentinfo">
          <span>Sunrise HES</span>
          <span className="ws-footer-sep">·</span>
          <span>Operational workspace</span>
        </footer>
      </div>
    </div>
  );
}

export function WorkspaceShell({ children }: WorkspaceShellProps) {
  return (
    <SessionProvider>
      <WorkspaceChrome>{children}</WorkspaceChrome>
    </SessionProvider>
  );
}

