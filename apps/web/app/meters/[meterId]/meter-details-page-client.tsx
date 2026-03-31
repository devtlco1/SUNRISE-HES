"use client";

import { OperationalShell } from "../../operational-shell";
import { MeterDetailsCommandsTab } from "./meter-details-commands-tab";

export function MeterDetailsPageClient({ meterId }: { meterId: string }) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title={`Meter Detail ${meterId}`}
      description="Blueprint-aligned meter detail surface with refined operational header context, recent command visibility, and execute-now actions for the stable command families."
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
