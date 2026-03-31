"use client";

import { OperationalHomeModule } from "./operational-home-module";
import { OperationalShell } from "./operational-shell";

export function OperationalHomePageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Operational Home / Dashboard MVP"
      description="Compact operational entrypoint tying together the current meters, commands, and connectivity slices."
    >
      {({ authorizedFetch }) => (
        <OperationalHomeModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
