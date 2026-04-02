"use client";

import { OperationalShell } from "../../operational-shell";
import { MeterImportModule } from "./meter-import-module";

export function MeterImportPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Meter Import Wizard MVP"
      description="Bounded CSV import flow for creating new meter records with a compact review step before submission."
    >
      {({ authorizedFetch }) => <MeterImportModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>
  );
}
