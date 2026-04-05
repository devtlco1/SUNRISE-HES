"use client";

import { OperationalShell } from "../operational-shell";
import { GisLiteModule } from "./gis-lite-module";

export function GisLitePageClient({
  initialMeterId,
}: {
  initialMeterId?: string | null;
}) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="GIS Lite MVP"
      description="Spatial visibility over existing platform entities using current meter, subscriber, and service-point context."
    >
      {({ authorizedFetch }) => (
        <GisLiteModule authorizedFetch={authorizedFetch} initialMeterId={initialMeterId} />
      )}
    </OperationalShell>
  );
}
