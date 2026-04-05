"use client";

import { OperationalHomeModule } from "./operational-home-module";
import { OperationalShell } from "./operational-shell";

export function OperationalHomePageClient() {
  return (
    <OperationalShell
      eyebrow="Dashboard Foundation"
      title="Operations Control Center"
      description="Phase 1 rebuilt dashboard home establishing the new admin-style shell, page rhythm, and launchpad experience."
      navigationVariant="dashboard-home"
    >
      {({ authorizedFetch }) => (
        <OperationalHomeModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
