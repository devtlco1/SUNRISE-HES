"use client";

import { OperationalShell } from "../operational-shell";
import { AccountsModule } from "./accounts-module";

export function AccountsPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Account Visibility MVP"
      description="Compact account-level visibility across existing subscriber, service-point, and meter linkage surfaces."
    >
      {({ authorizedFetch }) => <AccountsModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>
  );
}
