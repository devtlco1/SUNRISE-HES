"use client";

import { OperationalHomeModule } from "./operational-home-module";
import { OperationalShell } from "./operational-shell";

export function OperationalHomePageClient() {
  return (
    <OperationalShell
      eyebrow="Operations"
      title="Dashboard"
      description="Operational overview of fleet health, commands, alarms, readings, and network cues."
    >
      {({ authorizedFetch }) => (
        <OperationalHomeModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
