"use client";

import { CommandsModule } from "./commands-module";
import { OperationalShell } from "../operational-shell";

export function CommandsPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Global Commands MVP"
      description="Compact operational command visibility over the stable profile capture and relay control read models."
    >
      {({ authorizedFetch }) => <CommandsModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>
  );
}
