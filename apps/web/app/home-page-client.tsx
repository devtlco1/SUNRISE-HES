"use client";

import Link from "next/link";

import { useSession } from "./session-provider";
import { WorkspaceShell } from "./workspace-shell";

export function HomePageClient() {
  return (
    <WorkspaceShell>
      <HomeBody />
    </WorkspaceShell>
  );
}

function HomeBody() {
  const { currentUser, isCheckingSession } = useSession();

  if (isCheckingSession) {
    return <p className="ws-muted">Checking session…</p>;
  }

  if (!currentUser) {
    return (
      <div className="ws-canvas ws-canvas--gate">
        <p className="ws-muted">Sign in to open the workspace.</p>
        <Link href="/login" className="ws-btn ws-btn-primary">
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="ws-canvas">
      <h1 className="ws-page-title">Dashboard</h1>
      <p className="ws-page-subtitle">
        Empty workspace — modules will be added here as they are rebuilt.
      </p>
    </div>
  );
}
