"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { SessionProvider } from "./session-provider";

export function AuthEntryShell({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <SessionProvider>
      <main className="auth-page-shell">
        <section className="auth-page-hero">
          <div className="auth-page-copy">
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            <p className="lead">{description}</p>
            <div className="auth-page-badges">
              <span className="artifact-pill">Operationally focused</span>
              <span className="artifact-pill">Template-derived shell only</span>
              <span className="artifact-pill">Existing routes preserved</span>
            </div>
          </div>

          <div className="auth-page-card">
            <div className="auth-brand-block">
              <Link className="dashboard-brand-link" href="/">
                Sunrise HES
              </Link>
              <p className="muted">
                Product entry experience built over the current bounded operational
                platform.
              </p>
            </div>
            {children}
          </div>
        </section>
      </main>
    </SessionProvider>
  );
}
