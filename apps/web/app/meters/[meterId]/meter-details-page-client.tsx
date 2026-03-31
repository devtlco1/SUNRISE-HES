"use client";

import { OperationalShell } from "../../operational-shell";
import { MeterDetailsCommandsTab } from "./meter-details-commands-tab";

export function MeterDetailsPageClient({ meterId }: { meterId: string }) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title={`Meter ${meterId}`}
      description="Bounded meter details view with recent command visibility and execute-now actions for the stable operational command families."
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
