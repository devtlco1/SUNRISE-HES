"use client";

import { OperationalShell } from "../../operational-shell";
import { ServicePointDetailsModule } from "./service-point-details-module";

export function ServicePointDetailsPageClient({
  servicePointId,
}: {
  servicePointId: string;
}) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title={`Service Point ${servicePointId}`}
      description="Bounded service-point detail surface showing compact linked meter and subscriber context without expanding into billing or hierarchy redesign."
    >
      {({ authorizedFetch }) => (
        <ServicePointDetailsModule
          servicePointId={servicePointId}
          authorizedFetch={authorizedFetch}
        />
      )}
    </OperationalShell>
  );
}
