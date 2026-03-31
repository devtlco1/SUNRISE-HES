"use client";

import { OperationalShell } from "../operational-shell";
import { JobsEventsAlertsModule } from "./jobs-events-alerts-module";

export function JobsEventsAlertsPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Jobs / Events / Alerts MVP"
      description="Compact operational monitoring surface built from the current bounded job, command, and event read APIs."
    >
      {({ authorizedFetch }) => (
        <JobsEventsAlertsModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
