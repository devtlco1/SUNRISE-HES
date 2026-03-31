"use client";

import { OperationalShell } from "../../operational-shell";
import { TransformerSubstationDetailsModule } from "./transformer-substation-details-module";

export function TransformerSubstationDetailsPageClient({
  transformerId,
}: {
  transformerId: string;
}) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title={`Infrastructure ${transformerId}`}
      description="Bounded transformer and parent substation visibility with links into existing operational pages."
    >
      {({ authorizedFetch }) => (
        <TransformerSubstationDetailsModule
          transformerId={transformerId}
          authorizedFetch={authorizedFetch}
        />
      )}
    </OperationalShell>
  );
}
