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
          </div>

          <div className="auth-page-card">
            <div className="auth-brand-block">
              <Link className="dashboard-brand-link" href="/">
                Sunrise HES
              </Link>
              <p className="muted">Sign in to access the operational workspace.</p>
            </div>
            {children}
          </div>
        </section>
      </main>
    </SessionProvider>
  );
}
