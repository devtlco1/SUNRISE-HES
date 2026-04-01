"use client";

import { CommandsModule } from "./commands-module";
import { OperationalShell } from "../operational-shell";

export function CommandsPageClient({
  initialMeterIds = [],
}: {
  initialMeterIds?: string[];
}) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Global Commands MVP"
      description="Operational command visibility over the stable profile capture, relay control, and on-demand read command projections."
    >
      {({ authorizedFetch }) => (
        <CommandsModule authorizedFetch={authorizedFetch} initialMeterIds={initialMeterIds} />
      )}
    </OperationalShell>
  );
}
