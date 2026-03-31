"use client";

import { OperationalShell } from "../operational-shell";
import { SubscribersModule } from "./subscribers-module";

export function SubscribersPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Subscribers / Consumers MVP"
      description="Compact subscriber visibility slice for browsing consumer accounts and stepping into a bounded detail surface."
    >
      {({ authorizedFetch }) => (
        <SubscribersModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
