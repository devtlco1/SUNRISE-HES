"use client";

import { OperationalShell } from "../operational-shell";
import { ConnectivityModule } from "./connectivity-module";

export function ConnectivityPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Connectivity Overview MVP"
      description="Compact operational visibility into meter connectivity context with direct paths into the existing meter details experience."
    >
      {({ authorizedFetch }) => (
        <ConnectivityModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
