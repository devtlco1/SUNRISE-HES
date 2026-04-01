"use client";

import { OperationalShell } from "../operational-shell";
import { AccountsModule } from "./accounts-module";

export function AccountsPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Account Visibility MVP"
      description="Account visibility surface across existing subscriber, service-point, and meter linkage routes."
    >
      {({ authorizedFetch }) => <AccountsModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>
  );
}
