"use client";

import { OperationalShell } from "../operational-shell";
import { AuditCenterModule } from "./audit-center-module";

export function AuditCenterPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Traceability"
      title="Audit Center MVP"
      description="Operational traceability workspace built from the current persisted audit logs across auth, commands, jobs, meters, and related administration actions."
    >
      {({ authorizedFetch }) => <AuditCenterModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>
  );
}
