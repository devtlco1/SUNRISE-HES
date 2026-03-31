"use client";

import { OperationalHomeModule } from "./operational-home-module";
import { OperationalShell } from "./operational-shell";

export function OperationalHomePageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Operational Dashboard"
      description="Blueprint-aware product dashboard tying together the current operational, customer, GIS, and infrastructure modules."
    >
      {({ authorizedFetch }) => (
        <OperationalHomeModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
