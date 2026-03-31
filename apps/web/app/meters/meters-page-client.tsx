"use client";

import { OperationalShell } from "../operational-shell";
import { MetersModule } from "./meters-module";

export function MetersPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Meters Module MVP"
      description="Compact operational meter browse flow into the existing meter details and commands experience."
    >
      {({ authorizedFetch }) => <MetersModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>
  );
}
