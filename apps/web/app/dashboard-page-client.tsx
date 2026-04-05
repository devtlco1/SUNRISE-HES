"use client";

import { DashboardModule } from "./dashboard-module";
import { OperationalShell } from "./operational-shell";

export function DashboardPageClient() {
  return (
    <OperationalShell
      eyebrow="Sunrise HES"
      title="Dashboard"
      description="Blank operator canvas during frontend rebuild."
    >
      {() => <DashboardModule />}
    </OperationalShell>
  );
}
