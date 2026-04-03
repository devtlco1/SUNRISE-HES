"use client";

import { OperationalShell } from "../../operational-shell";
import { MeterDetailsCommandsTab } from "./meter-details-commands-tab";

export function MeterDetailsPageClient({ meterId }: { meterId: string }) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Meter Detail Workspace"
      description="Blueprint-aligned meter detail foundation for one meter across summary, connectivity, readings, and commands using the existing operational data contract."
      currentMeterId={meterId}
    >
      {({ authorizedFetch }) => (
        <MeterDetailsCommandsTab
          meterId={meterId}
          authorizedFetch={authorizedFetch}
        />
      )}
    </OperationalShell>
  );
}
