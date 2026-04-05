"use client";

import { OperationalShell } from "../operational-shell";
import { MetersModule } from "./meters-module";

export function MetersPageClient() {
  return (
    <OperationalShell
      eyebrow="Operations"
      title="Meters"
      description="Authoritative inventory and operational registry for meter fleet review."
    >
      {({ authorizedFetch }) => <MetersModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>
  );
}
