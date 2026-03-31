"use client";

import { OperationalShell } from "../operational-shell";
import { ServicePointsModule } from "./service-points-module";

export function ServicePointsPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Service Points / Premises MVP"
      description="Compact service-point and premise visibility built from current meter, subscriber, and location read surfaces."
    >
      {({ authorizedFetch }) => (
        <ServicePointsModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
