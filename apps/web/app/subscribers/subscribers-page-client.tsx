"use client";

import { OperationalShell } from "../operational-shell";
import { SubscribersModule } from "./subscribers-module";

export function SubscribersPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Subscribers / Consumers MVP"
      description="Subscriber visibility surface for browsing consumer linkage and stepping into a bounded detail route."
    >
      {({ authorizedFetch }) => (
        <SubscribersModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
