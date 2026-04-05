"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { DashboardHomeView } from "./dashboard/dashboard-home-view";
import {
  fetchDashboardSnapshot,
  type DashboardSnapshot,
} from "./dashboard/fetch-dashboard-data";
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
  const { currentUser, isCheckingSession, authorizedFetch } = useSession();
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const next = await fetchDashboardSnapshot(authorizedFetch);
      setSnapshot(next);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Dashboard snapshot failed.";
      setLoadError(message);
      setSnapshot(null);
    } finally {
      setLoading(false);
    }
  }, [authorizedFetch]);

  useEffect(() => {
    if (!currentUser) {
      setSnapshot(null);
      setLoadError(null);
      setLoading(false);
      return;
    }
    void load();
  }, [currentUser, load]);

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

  return <DashboardHomeView snapshot={snapshot} loading={loading} loadError={loadError} />;
}
