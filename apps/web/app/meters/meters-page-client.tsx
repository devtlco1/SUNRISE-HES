"use client";

import { OperationalShell } from "../operational-shell";
import { MetersModule } from "./meters-module";

export function MetersPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Meters Registry"
      description="Authoritative operational inventory surface for browsing meters and continuing into the blueprint-critical meter details experience."
    >
      {({ authorizedFetch }) => <MetersModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>
  );
}
