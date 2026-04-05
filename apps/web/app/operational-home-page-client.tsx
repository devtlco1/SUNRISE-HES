"use client";

import { OperationalHomeModule } from "./operational-home-module";
import { OperationalShell } from "./operational-shell";

export function OperationalHomePageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Operational Dashboard"
      description="Operator-first overview tying together the current operational, commercial, GIS, and infrastructure workspaces."
    >
      {({ authorizedFetch }) => (
        <OperationalHomeModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
