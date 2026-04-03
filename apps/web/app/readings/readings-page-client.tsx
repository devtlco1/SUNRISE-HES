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
      eyebrow="Operational Reports"
      title="Reports Workspace"
      description="Shell-aligned reporting surface for bounded readings visibility, review queues, and meter-level report context using the existing readings contracts."
    >
      {({ authorizedFetch }) => (
        <ReadingsModule authorizedFetch={authorizedFetch} initialMeterId={initialMeterId} />
      )}
    </OperationalShell>
  );
}
