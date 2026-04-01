"use client";

import { OperationalShell } from "../operational-shell";
import { ReadingsModule } from "./readings-module";

export function ReadingsPageClient({
  initialMeterId = null,
}: {
  initialMeterId?: string | null;
}) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Readings Overview MVP"
      description="Phase 2 entry slice for bounded readings visibility, starting with a shell-aligned overview and billing reads for the current meter scope."
    >
      {({ authorizedFetch }) => (
        <ReadingsModule authorizedFetch={authorizedFetch} initialMeterId={initialMeterId} />
      )}
    </OperationalShell>
  );
}
