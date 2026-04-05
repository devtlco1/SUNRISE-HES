"use client";

import { DashboardModule } from "./dashboard-module";
import { OperationalShell } from "./operational-shell";

export function DashboardPageClient() {
  return (
    <OperationalShell
      eyebrow="Operations control"
      title="AMI command desk"
      description="Fleet posture, remote actions, and live exceptions from the current meter sample."
    >
      {({ authorizedFetch }) => <DashboardModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>
  );
}
